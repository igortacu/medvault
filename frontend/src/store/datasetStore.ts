import { create } from 'zustand';
import type {
  MedicalRecord,
  Institution,
  InstitutionConnection,
  MedicalRecordFilters,
} from '../api/types.ts';
import { datasetApi } from '../api';

interface DatasetState {
  patientId: string | null;
  diagnostics: MedicalRecord[];
  prescriptions: MedicalRecord[];
  certificates: MedicalRecord[];
  otherMedicalInfo: MedicalRecord[];
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];

  filters: {
    diagnostics: MedicalRecordFilters;
    prescriptions: MedicalRecordFilters;
    certificates: MedicalRecordFilters;
    otherMedicalInfo: MedicalRecordFilters;
  };

  // State
  isLoading: boolean;
  error: string | null;

  // Actions
  loadDataset: () => Promise<void>;
  loadCategory: (
    category:
      'diagnostics' | 'prescriptions' | 'certificates' | 'otherMedicalInfo'
  ) => Promise<void>;
  setFilters: (
    category: keyof DatasetState['filters'],
    filters: MedicalRecordFilters
  ) => void;

  addInstitutionConnection: (institutionId: string) => Promise<void>;
  completeInstitutionConnection: (connectionId: string) => Promise<void>;
  revokeInstitutionConnection: (connectionId: string) => Promise<void>;
}

export const useDatasetStore = create<DatasetState>((set, get) => ({
  // Initial data
  patientId: null,
  diagnostics: [],
  prescriptions: [],
  certificates: [],
  otherMedicalInfo: [],
  institutions: [],
  institutionConnections: [],

  filters: {
    diagnostics: {},
    prescriptions: {},
    certificates: {},
    otherMedicalInfo: {},
  },
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
      const patientId = user.id;

      // 'diagnoses' and 'analyses' are two distinct DataCategory values but
      // share the single "Diagnostics" tab in the UI, so they're merged here.
      const [
        diagnoses,
        analyses,
        prescriptions,
        certificates,
        otherMedicalInfo,
        institutions,
        institutionConnections,
      ] = await Promise.all([
        datasetApi.getCategoryRecords(patientId, 'diagnoses'),
        datasetApi.getCategoryRecords(patientId, 'analyses'),
        datasetApi.getCategoryRecords(patientId, 'prescriptions'),
        datasetApi.getCategoryRecords(patientId, 'certificates'),
        datasetApi.getCategoryRecords(patientId, 'other_med_info'),
        datasetApi.getInstitutions(),
        datasetApi.getConnections(patientId),
      ]);

      set({
        patientId,
        diagnostics: [...diagnoses, ...analyses].sort((a, b) =>
          (b.date ?? '').localeCompare(a.date ?? '')
        ),
        prescriptions,
        certificates,
        otherMedicalInfo,
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
    const { patientId, filters } = get();

    if (!patientId) return;

    set({
      isLoading: true,
      error: null,
    });

    try {
      if (category === 'diagnostics') {
        const [diagnoses, analyses] = await Promise.all([
          datasetApi.getCategoryRecords(
            patientId,
            'diagnoses',
            filters.diagnostics
          ),
          datasetApi.getCategoryRecords(
            patientId,
            'analyses',
            filters.diagnostics
          ),
        ]);

        set({
          diagnostics: [...diagnoses, ...analyses].sort((a, b) =>
            (b.date ?? '').localeCompare(a.date ?? '')
          ),
          isLoading: false,
        });
      }

      if (category === 'prescriptions') {
        const records = await datasetApi.getCategoryRecords(
          patientId,
          'prescriptions',
          filters.prescriptions
        );

        set({
          prescriptions: records,
          isLoading: false,
        });
      }

      if (category === 'certificates') {
        const records = await datasetApi.getCategoryRecords(
          patientId,
          'certificates',
          filters.certificates
        );

        set({
          certificates: records,
          isLoading: false,
        });
      }

      if (category === 'otherMedicalInfo') {
        const records = await datasetApi.getCategoryRecords(
          patientId,
          'other_med_info',
          filters.otherMedicalInfo
        );

        set({
          otherMedicalInfo: records,
          isLoading: false,
        });
      }
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error ? error.message : 'Failed to load category',
      });
    }
  },

  setFilters: (category, filters) => {
    set((state) => ({
      filters: {
        ...state.filters,
        [category]: filters,
      },
    }));
  },

  addInstitutionConnection: async (institutionId) => {
    const { patientId } = get();
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
    const { patientId } = get();
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
        institutionConnections: state.institutionConnections.map((existing) =>
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
        institutionConnections: state.institutionConnections.map((existing) =>
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
}));
