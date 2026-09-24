import type { DataCategory } from '../api/types';
import type { CareRecipient } from '../api/caregiver.types';

/** The record lists kept in datasetStore, one per documents tab. */
export type RecordTab =
  'diagnostics' | 'prescriptions' | 'certificates' | 'otherMedicalInfo';

/**
 * The DataCategories behind each tab. Diagnostics merges two categories, so
 * a recipient sharing either one is enough to see the tab.
 */
export const TAB_CATEGORIES: Record<RecordTab, DataCategory[]> = {
  diagnostics: ['diagnoses', 'analyses'],
  prescriptions: ['prescriptions'],
  certificates: ['certificates'],
  otherMedicalInfo: ['other_med_info'],
};

export const TAB_PATHS: Record<RecordTab, string> = {
  diagnostics: '/documents',
  prescriptions: '/documents/prescriptions',
  certificates: '/documents/certificates',
  otherMedicalInfo: '/documents/other_medications',
};

/**
 * Whether the viewer may see a category. With no active recipient the user
 * is in their own vault and sees everything; otherwise only what the
 * recipient granted. This only drives the UI — the backend enforces access.
 */
export function canViewCategory(
  recipient: CareRecipient | null,
  category: DataCategory
): boolean {
  if (!recipient) return true;
  return recipient.permissions.some(
    (p) => p.category === category && p.granted
  );
}

export function canViewTab(
  recipient: CareRecipient | null,
  tab: RecordTab
): boolean {
  return TAB_CATEGORIES[tab].some((category) =>
    canViewCategory(recipient, category)
  );
}

/** Where to land after switching into a recipient's vault. */
export function firstAllowedPath(recipient: CareRecipient): string {
  const tab = (Object.keys(TAB_PATHS) as RecordTab[]).find((t) =>
    canViewTab(recipient, t)
  );
  if (tab) return TAB_PATHS[tab];
  if (canViewCategory(recipient, 'patient_info')) return '/profile';
  return '/recipients';
}
