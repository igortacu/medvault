// records.ts
// MedicalRecord helpers shared by the mock and real services, so a category
// page labels and filters records identically against either.

import type {
  MedicalRecord,
  MedicalRecordFilters,
  ResourceTypeLabelMap,
} from './types';

const resourceTypeLabels: ResourceTypeLabelMap = {
  Patient: 'Patient record',
  Condition: 'Diagnosis',
  Observation: 'Lab result',
  DiagnosticReport: 'Diagnostic report',
  MedicationRequest: 'Prescription',
  AllergyIntolerance: 'Allergy',
  Encounter: 'Hospitalization',
  DocumentReference: 'Uploaded document',
};

export function labelForResourceType(resourceType: string): string {
  return (
    (resourceTypeLabels as unknown as Record<string, string>)[resourceType] ??
    resourceType
  );
}

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
