import { create } from 'zustand';
import type {
  MedicalRecord,
  Institution,
  InstitutionConnection,
  MedicalRecordFilters,
  User,
  PatientProfile,
} from '../api/types.ts';
import type { CareRecipient } from '../api/caregiver.types.ts';
import { caregiverApi, datasetApi } from '../api';
import {
  canViewCategory,
  TAB_CATEGORIES,
  type RecordTab,
} from '../lib/recipientAccess.ts';

const ACTIVE_RECIPIENT_KEY = 'medvault.activeRecipientLinkId';
const RECORD_TABS = Object.keys(TAB_CATEGORIES) as RecordTab[];

// sessionStorage can throw (private mode, blocked storage); the switch then
// just doesn't survive a reload.
function readStoredLinkId(): string | null {
  try {
    return sessionStorage.getItem(ACTIVE_RECIPIENT_KEY);
  } catch {
    return null;
  }
}

function storeLinkId(linkId: string | null) {
  try {
    if (linkId) sessionStorage.setItem(ACTIVE_RECIPIENT_KEY, linkId);
    else sessionStorage.removeItem(ACTIVE_RECIPIENT_KEY);
  } catch {
    // ignore
  }
}

/** Restores a switch from before a reload, if that link is still active. */
async function resolveStoredRecipient(
  caregiverUserId: string
): Promise<CareRecipient | null> {
  const linkId = readStoredLinkId();
  if (!linkId) return null;
  try {
    const recipients = await caregiverApi.getUsersICareFor(caregiverUserId);
    const recipient = recipients.find(
      (r) => r.linkId === linkId && r.status === 'active'
    );
    if (!recipient) storeLinkId(null);
    return recipient ?? null;
  } catch {
    return null;
  }
}

/**
 * Fetches one tab's records, skipping categories the recipient hasn't shared.
 * 'diagnoses' and 'analyses' are two distinct DataCategory values but share
 * the single "Diagnostics" tab in the UI, so they're merged here.
 */
async function fetchTab(
  patientId: string,
  tab: RecordTab,
  recipient: CareRecipient | null,
  filters?: MedicalRecordFilters
): Promise<MedicalRecord[]> {
  const categories = TAB_CATEGORIES[tab].filter((category) =>
    canViewCategory(recipient, category)
  );
  const results = await Promise.all(
    categories.map((category) =>
      datasetApi.getCategoryRecords(patientId, category, filters)
    )
  );
  const records = results.flat();
  return tab === 'diagnostics'
    ? records.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
    : records;
}

async function fetchAllTabs(
  patientId: string,
  recipient: CareRecipient | null
): Promise<Record<RecordTab, MedicalRecord[]>> {
  const lists = await Promise.all(
    RECORD_TABS.map((tab) => fetchTab(patientId, tab, recipient))
  );
  return Object.fromEntries(
    RECORD_TABS.map((tab, i) => [tab, lists[i]])
  ) as Record<RecordTab, MedicalRecord[]>;
}

async function fetchRecipientProfile(
  recipient: CareRecipient | null
): Promise<PatientProfile | null> {
  if (!recipient || !canViewCategory(recipient, 'patient_info')) return null;
  return datasetApi.getPatientProfile(recipient.patientId);
}

const emptyFilters = (): Record<RecordTab, MedicalRecordFilters> => ({
  diagnostics: {},
  prescriptions: {},
  certificates: {},
  otherMedicalInfo: {},
});

const emptyRecords = (): Record<RecordTab, MedicalRecord[]> => ({
  diagnostics: [],
  prescriptions: [],
  certificates: [],
  otherMedicalInfo: [],
});

interface DatasetState {
  /** Whose records are shown: the current user, or the active recipient. */
  patientId: string | null;
  currentUser: User | null;
  /** Always the logged-in user's own profile. */
  patientProfile: PatientProfile | null;
  /** Set while viewing a recipient's vault as their caregiver. */
  activeRecipient: CareRecipient | null;
  /** The active recipient's profile, when they've shared patient_info. */
  recipientProfile: PatientProfile | null;
  diagnostics: MedicalRecord[];
  prescriptions: MedicalRecord[];
  certificates: MedicalRecord[];
  otherMedicalInfo: MedicalRecord[];
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];

  filters: Record<RecordTab, MedicalRecordFilters>;

  // State
  isLoading: boolean;
  error: string | null;

  // Actions
  loadDataset: () => Promise<void>;
  loadCategory: (category: RecordTab) => Promise<void>;
  setFilters: (
    category: keyof DatasetState['filters'],
    filters: MedicalRecordFilters
  ) => void;

  switchToRecipient: (recipient: CareRecipient) => Promise<void>;
  switchToSelf: () => Promise<void>;

  addInstitutionConnection: (institutionId: string) => Promise<void>;
  completeInstitutionConnection: (connectionId: string) => Promise<void>;
  revokeInstitutionConnection: (connectionId: string) => Promise<void>;
}

export const useDatasetStore = create<DatasetState>((set, get) => {
  /**
   * Points the vault at `recipient` (or back at the current user) and
   * reloads every tab. Lists are cleared first so one person's records never
   * show under another's name while the new ones load.
   */
  const enterVault = async (recipient: CareRecipient | null) => {
    const { currentUser } = get();
    if (!currentUser) return;
    const patientId = recipient?.patientId ?? currentUser.id;

    storeLinkId(recipient?.linkId ?? null);
    set({
      activeRecipient: recipient,
      patientId,
      recipientProfile: null,
      ...emptyRecords(),
      filters: emptyFilters(),
      isLoading: true,
      error: null,
    });

    try {
      const [records, recipientProfile] = await Promise.all([
        fetchAllTabs(patientId, recipient),
        fetchRecipientProfile(recipient),
      ]);
      // A newer switch started while this one was loading.
      if (get().patientId !== patientId) return;
      set({ ...records, recipientProfile, isLoading: false });
    } catch (error) {
      if (get().patientId !== patientId) return;
      set({
        isLoading: false,
        error:
          error instanceof Error ? error.message : 'Failed to load records',
      });
    }
  };

  return {
    // Initial data
    patientId: null,
    currentUser: null,
    patientProfile: null,
    activeRecipient: null,
    recipientProfile: null,
    ...emptyRecords(),
    institutions: [],
    institutionConnections: [],

    filters: emptyFilters(),
    // Initial state
    isLoading: false,
    error: null,

    loadDataset: async () => {
      set({
        isLoading: true,
        error: null,
      });
      try {
        const user = await datasetApi.getCurrentUser();
        const recipient = await resolveStoredRecipient(user.id);
        const patientId = recipient?.patientId ?? user.id;

        const [
          records,
          recipientProfile,
          institutions,
          institutionConnections,
          patientProfile,
        ] = await Promise.all([
          fetchAllTabs(patientId, recipient),
          fetchRecipientProfile(recipient),
          datasetApi.getInstitutions(),
          datasetApi.getConnections(user.id),
          datasetApi.getPatientProfile(user.id),
        ]);

        set({
          patientId,
          currentUser: user,
          patientProfile,
          activeRecipient: recipient,
          recipientProfile,
          ...records,
          institutions,
          institutionConnections,
          isLoading: false,
        });
      } catch (error) {
        set({
          isLoading: false,
          error:
            error instanceof Error ? error.message : 'Failed to load dataset',
        });
      }
    },

    loadCategory: async (category) => {
      const { patientId, filters, activeRecipient } = get();

      if (!patientId) return;

      set({
        isLoading: true,
        error: null,
      });

      try {
        const records = await fetchTab(
          patientId,
          category,
          activeRecipient,
          filters[category]
        );
        if (get().patientId !== patientId) return;
        set({ [category]: records, isLoading: false });
      } catch (error) {
        set({
          isLoading: false,
          error:
            error instanceof Error ? error.message : 'Failed to load category',
        });
      }
    },

    switchToRecipient: (recipient) => enterVault(recipient),
    switchToSelf: () => enterVault(null),

    setFilters: (category, filters) => {
      set((state) => ({
        filters: {
          ...state.filters,
          [category]: filters,
        },
      }));
    },

    addInstitutionConnection: async (institutionId) => {
      // Institutions always belong to the logged-in user, even mid-switch.
      const patientId = get().currentUser?.id;
      if (!patientId) return;

      set({
        isLoading: true,
        error: null,
      });

      try {
        const connection = await datasetApi.connectInstitution(
          patientId,
          institutionId
        );
        set((state) => ({
          institutionConnections: [...state.institutionConnections, connection],
          isLoading: false,
        }));
      } catch (error) {
        set({
          isLoading: false,
          error:
            error instanceof Error
              ? error.message
              : 'Failed to connect institution',
        });
      }
    },
    revokeInstitutionConnection: async (connectionId) => {
      const patientId = get().currentUser?.id;
      if (!patientId) return;

      set({
        isLoading: true,
        error: null,
      });

      try {
        const connection = await datasetApi.revokeConnection(connectionId);
        if (!connection) {
          throw new Error('Connection not found');
        }
        set((state) => ({
          institutionConnections: state.institutionConnections.map(
            (existing) =>
              existing.id === connection.id ? connection : existing
          ),
          isLoading: false,
        }));
      } catch (error) {
        set({
          isLoading: false,
          error:
            error instanceof Error
              ? error.message
              : 'Failed to revoke institution connection',
        });
      }
    },

    completeInstitutionConnection: async (connectionId) => {
      set({
        isLoading: true,
        error: null,
      });

      try {
        const connection =
          await datasetApi.authorizeInstitutionConnection(connectionId);

        if (!connection) {
          throw new Error('Connection not found');
        }

        set((state) => ({
          institutionConnections: state.institutionConnections.map(
            (existing) =>
              existing.id === connection.id ? connection : existing
          ),
          isLoading: false,
        }));
      } catch (error) {
        set({
          isLoading: false,
          error:
            error instanceof Error
              ? error.message
              : 'Failed to authorize institution',
        });
      }
    },
  };
});
