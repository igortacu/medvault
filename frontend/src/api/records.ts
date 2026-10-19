// records.ts
// MedicalRecord helpers shared by the mock and real services, so a category
// page filters records identically against either. Labels for record codes
// live in the UI (features/documents/recordLabels.ts), per language.

import type { MedicalRecord, MedicalRecordFilters } from './types';

export function filterRecords(
  records: MedicalRecord[],
  filters?: MedicalRecordFilters
): MedicalRecord[] {
  if (!filters) return records;

  return records.filter((record) => {
    if (
      filters.search &&
      !record.title.toLowerCase().includes(filters.search.toLowerCase())
    ) {
      return false;
    }

    if (
      filters.documentTypeCode &&
      record.documentTypeCode !== filters.documentTypeCode
    ) {
      return false;
    }

    if (
      filters.institutionId &&
      record.institutionId !== filters.institutionId
    ) {
      return false;
    }

    if (filters.source && record.source !== filters.source) {
      return false;
    }

    if (filters.dateFrom && record.date) {
      if (record.date < filters.dateFrom) return false;
    }

    if (filters.dateTo && record.date) {
      if (record.date > filters.dateTo) return false;
    }

    return true;
  });
}
