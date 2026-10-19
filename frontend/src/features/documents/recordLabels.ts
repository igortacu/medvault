import type { MedicalRecord } from '../../api/types.ts';
import i18n from '../../i18n';

// Records carry codes (document subtype, FHIR resourceType, source); these turn
// them into text in the active language. Unknown codes are shown as they are.

/** A document subtype code such as "blood_test", e.g. "Analiza sângelui". */
export const documentTypeLabel = (code: string): string =>
  i18n.t(`documents:docType.${code}`, { defaultValue: code });

/**
 * The kind of record: its document subtype when known (e.g. "Vaccination
 * certificate"), else its FHIR resourceType (e.g. "Lab result"). The subtype
 * comes first because a resourceType like DocumentReference says nothing
 * about the record, and its label reads as "uploaded" even for an
 * institution's document.
 */
export function recordTypeLabel(record: MedicalRecord): string {
  const code = record.documentTypeCode;
  if (code && i18n.exists(`documents:docType.${code}`)) {
    return documentTypeLabel(code);
  }
  return i18n.t(`documents:resourceType.${record.resourceType}`, {
    defaultValue: record.resourceType,
  });
}

/** The record's title; one that fell back to its subtype code gets the label. */
export function recordTitle(record: MedicalRecord): string {
  if (record.documentTypeCode && record.title === record.documentTypeCode) {
    return documentTypeLabel(record.documentTypeCode);
  }
  if (record.title === record.resourceType) return recordTypeLabel(record);
  return record.title;
}

/** The institution's name, or "Self-uploaded" in the active language. */
export const recordSource = (record: MedicalRecord): string =>
  record.source === 'self_uploaded'
    ? i18n.t('documents:filter.selfUploaded')
    : record.sourceLabel;
