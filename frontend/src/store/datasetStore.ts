import { create } from 'zustand';
import type {
  Certificate,
  Diagnostic,
  Document,
  Institution,
  InstitutionConnection,
  OtherMedicalInfo,
  Prescription,
} from '../api/types.ts';
import { datasetApi } from '../api';

interface DatasetState {
  diagnostics: Diagnostic[];
  documents: Document[];
  prescriptions: Prescription[];
  certificates: Certificate[];
  otherMedicalInfo: OtherMedicalInfo[];
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];

  // State
  isLoading: boolean;
  error: string | null;

  // Actions
  loadDataset: (userId: string) => Promise<void>;
}

export const useDatasetStore = create<DatasetState>((set) => ({
  // Initial data
  diagnostics: [],
  documents: [],
  prescriptions: [],
  certificates: [],
  otherMedicalInfo: [],
  institutions: [],
  institutionConnections: [],

  // Initial state
  isLoading: false,
  error: null,

  loadDataset: async (userId) => {
    set({
      isLoading: true,
      error: null,
    });
    try {
      const [
        diagnostics,
        documents,
        prescriptions,
        certificates,
        otherMedicalInfo,
        institutions,
        institutionConnections,
      ] = await Promise.all([
        datasetApi.getDiagnostics(userId),
        datasetApi.getDocuments(userId),
        datasetApi.getPrescriptions(userId),
        datasetApi.getCertificates(userId),
        datasetApi.getOtherMedicalInfo(userId),
        datasetApi.getInstitutions(),
        datasetApi.getInstitutionConnections(userId),
      ]);
      set({
        diagnostics,
        documents,
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
