import { create } from 'zustand';
import type {
  MedicalRecord,
  Institution,
  InstitutionConnection,
  MedicalRecordFilters,
  User,
  PatientProfile,
  SourceState,
  SourceStatus,
} from '../api/types.ts';
import type { CareRecipient } from '../api/caregiver.types.ts';
import { caregiverApi, datasetApi } from '../api';
import { isUnauthorized } from '../api/errors.ts';
import {
  canViewCategory,
  TAB_CATEGORIES,
  type RecordTab,
} from '../lib/recipientAccess.ts';

const ACTIVE_RECIPIENT_KEY = 'medvault.activeRecipientLinkId';
// Version of the consent text shown before connecting an institution; stored
// by the backend alongside the connection.
const CONSENT_TEXT_VERSION = '2026-09';
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
): Promise<{ records: MedicalRecord[]; sources: SourceStatus[] }> {
  const categories = TAB_CATEGORIES[tab].filter((category) =>
    canViewCategory(recipient, category)
  );
  const results = await Promise.all(
    categories.map((category) =>
      datasetApi.getCategoryRecords(patientId, category, filters)
    )
  );
  const records = results.flatMap((r) => r.records);
  // Several categories share a tab; one entry per institution, worst state wins.
  const sources = mergeSources(results.flatMap((r) => r.sources));
  return {
    records:
      tab === 'diagnostics'
        ? records.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
        : records,
    sources,
  };
}

const SOURCE_SEVERITY: Record<SourceState, number> = {
  ok: 0,
  needs_reconnect: 1,
  timeout: 2,
  unavailable: 3,
  unauthorised: 4,
};

function mergeSources(sources: SourceStatus[]): SourceStatus[] {
  const byInstitution = new Map<string, SourceStatus>();
  for (const source of sources) {
    const existing = byInstitution.get(source.institutionId);
    if (!existing) {
      byInstitution.set(source.institutionId, { ...source });
      continue;
    }
    existing.count += source.count;
    if (SOURCE_SEVERITY[source.status] > SOURCE_SEVERITY[existing.status]) {
      existing.status = source.status;
    }
  }
  return [...byInstitution.values()];
}

async function fetchAllTabs(
  patientId: string,
  recipient: CareRecipient | null
): Promise<
  Record<RecordTab, MedicalRecord[]> & {
    sources: Record<RecordTab, SourceStatus[]>;
  }
> {
  const results = await Promise.all(
    RECORD_TABS.map((tab) => fetchTab(patientId, tab, recipient))
  );
  const entries = RECORD_TABS.map((tab, i) => [tab, results[i]] as const);
  return {
    ...(Object.fromEntries(
      entries.map(([tab, r]) => [tab, r.records])
    ) as Record<RecordTab, MedicalRecord[]>),
    sources: Object.fromEntries(
      entries.map(([tab, r]) => [tab, r.sources])
    ) as Record<RecordTab, SourceStatus[]>,
  };
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

const emptyRecords = () => ({
  diagnostics: [] as MedicalRecord[],
  prescriptions: [] as MedicalRecord[],
  certificates: [] as MedicalRecord[],
  otherMedicalInfo: [] as MedicalRecord[],
  sources: {
    diagnostics: [],
    prescriptions: [],
    certificates: [],
    otherMedicalInfo: [],
  } as Record<RecordTab, SourceStatus[]>,
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
  /** How each connected institution answered, per tab (for the status banner). */
  sources: Record<RecordTab, SourceStatus[]>;
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];

  filters: Record<RecordTab, MedicalRecordFilters>;

  // State
  isLoading: boolean;
  error: string | null;
  /** The backend has no valid session for this browser. */
  needsLogin: boolean;

  // Actions
  loadDataset: () => Promise<void>;
  /** Ends the session and reloads into /login, dropping all in-memory state. */
  logout: () => Promise<void>;
  loadCategory: (category: RecordTab) => Promise<void>;
  setFilters: (
    category: keyof DatasetState['filters'],
    filters: MedicalRecordFilters
  ) => void;

  switchToRecipient: (recipient: CareRecipient) => Promise<void>;
  switchToSelf: () => Promise<void>;

  /** Starts the OAuth connect flow; resolves to the URL the browser should
   * be sent to, or null if it could not be started. */
  addInstitutionConnection: (
    institutionId: string,
    consentTextVersion?: string
  ) => Promise<string | null>;
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
    needsLogin: false,

    loadDataset: async () => {
      set({
        isLoading: true,
        error: null,
        needsLogin: false,
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
          datasetApi.getConnections(),
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
        if (isUnauthorized(error)) {
          set({ isLoading: false, needsLogin: true });
          return;
        }
        set({
          isLoading: false,
          error:
            error instanceof Error ? error.message : 'Failed to load dataset',
        });
      }
    },

    logout: async () => {
      try {
        await datasetApi.logout();
      } catch {
        // The session is gone either way once the cookie is ignored.
      }
      storeLinkId(null);
      window.location.assign('/login');
    },

    loadCategory: async (category) => {
      const { patientId, filters, activeRecipient } = get();

      if (!patientId) return;

      set({
        isLoading: true,
        error: null,
      });

      try {
        const { records, sources } = await fetchTab(
          patientId,
          category,
          activeRecipient,
          filters[category]
        );
        if (get().patientId !== patientId) return;
        set((state) => ({
          [category]: records,
          sources: { ...state.sources, [category]: sources },
          isLoading: false,
        }));
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

    addInstitutionConnection: async (
      institutionId,
      consentTextVersion = CONSENT_TEXT_VERSION
    ) => {
      // Institutions always belong to the logged-in user, even mid-switch.
      const idnp = get().patientProfile?.idnp;
      if (!idnp) {
        set({ error: 'Missing IDNP for institution connection' });
        return null;
      }

      set({
        isLoading: true,
        error: null,
      });

      try {
        const { authorize_url } = await datasetApi.connectInstitution(
          institutionId,
          idnp,
          consentTextVersion
        );
        const institutionConnections = await datasetApi.getConnections();
        set({ institutionConnections, isLoading: false });
        return authorize_url;
      } catch (error) {
        set({
          isLoading: false,
          error:
            error instanceof Error
              ? error.message
              : 'Failed to connect institution',
        });
        return null;
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
        await datasetApi.revokeConnection(connectionId);
        const revokedAt = new Date().toISOString();
        set((state) => ({
          institutionConnections: state.institutionConnections.map(
            (existing) =>
              existing.id === connectionId
                ? { ...existing, status: 'revoked', revoked_at: revokedAt }
                : existing
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
