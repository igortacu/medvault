import type { DataCategory } from '../../api/types';
import i18n from '../../i18n';

export const DATA_CATEGORIES: DataCategory[] = [
  'diagnoses',
  'certificates',
  'analyses',
  'prescriptions',
  'patient_info',
  'other_med_info',
];

/** A category's name in the active language, e.g. "Diagnoses". */
export const categoryLabel = (category: DataCategory): string =>
  i18n.t(`common:category.${category}`);
