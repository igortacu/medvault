import { create } from 'zustand';
import type {
  MedicalRecord,
  Institution,
  InstitutionConnection,
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

  // State
  isLoading: boolean;
  error: string | null;

  // Actions
  loadDataset: () => Promise<void>;
}

export const useDatasetStore = create<DatasetState>((set) => ({
  // Initial data
  patientId: null,
  diagnostics: [],
  prescriptions: [],
  certificates: [],
  otherMedicalInfo: [],
  institutions: [],
  institutionConnections: [],

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
}));
