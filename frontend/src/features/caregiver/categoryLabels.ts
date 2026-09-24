import type { DataCategory } from '../../api/types';

export const CATEGORY_LABELS: Record<DataCategory, string> = {
  diagnoses: 'Diagnoses',
  certificates: 'Certificates',
  analyses: 'Analyses',
  prescriptions: 'Prescriptions',
  patient_info: 'Patient info',
  other_med_info: 'Other medical information',
};
