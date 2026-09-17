// mockDataService.ts
// Frontend-only stand-in for the real backend. Reads seed.json (which itself
// mirrors the real app DB tables + the mock institutional/FHIR data) and
// returns data shaped exactly like realDataService.ts would, including the
// same category-unification logic the real API is supposed to do:
// self-uploaded documents and institutional FHIR resources both resolve
// their "category" through document_types, so the frontend never needs to
// know which source a record came from.
//
// Requires "resolveJsonModule": true (and ideally "esModuleInterop": true)
// in tsconfig.json so seed.json can be imported directly.

import seed from '../mocks/seed.json';
import type {
  SeedData,
  DatasetService,
  DataCategory,
  FhirResource,
  Institution,
  InstitutionConnection,
  SelfUploadedDocument,
  MedicalRecord,
  ResourceTypeLabelMap,
  UploadDocumentInput,
  DataExport,
} from './types';

const data = seed as unknown as SeedData;

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

function labelForResourceType(resourceType: string): string {
  return (
    (resourceTypeLabels as unknown as Record<string, string>)[resourceType] ??
    resourceType
  );
}

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const delay = (ms = 250): Promise<void> =>
  new Promise((res) => setTimeout(res, ms));

function categoryForCode(code: string | null): DataCategory | null {
  if (!code) return null;
  const dt = data.appDb.document_types.find((d) => d.code === code);
  return dt ? dt.category : null;
}

function labelForCode(code: string | null): string | null {
  if (!code) return null;
  const dt = data.appDb.document_types.find((d) => d.code === code);
  return dt ? dt.label : null;
}

function toRecord(
  resource: FhirResource,
  institution: Institution
): MedicalRecord {
  const code = resource.category?.coding?.[0]?.code ?? null;
  return {
    id: `${institution.id}/${resource.resourceType}/${resource.id}`,
    source: 'institution',
    sourceLabel: institution.name,
    institutionId: institution.id,
    category: categoryForCode(code),
    documentTypeCode: code,
    resourceType: resource.resourceType,
    type: labelForResourceType(resource.resourceType),
    title:
      resource.code?.text ||
      resource.medicationCodeableConcept?.text ||
      (typeof resource.conclusion === 'string' ? resource.conclusion : null) ||
      labelForCode(code) ||
      resource.resourceType,
    date:
      resource.effectiveDateTime ||
      resource.recordedDate ||
      resource.authoredOn ||
      resource.period?.start ||
      null,
    raw: resource,
  };
}

function selfUploadedToRecord(doc: SelfUploadedDocument): MedicalRecord {
  return {
    id: doc.id,
    source: 'self_uploaded',
    sourceLabel: 'Self-uploaded',
    institutionId: null,
    category: categoryForCode(doc.document_type_code),
    documentTypeCode: doc.document_type_code,
    resourceType: 'DocumentReference',
    type: labelForResourceType('DocumentReference'),
    title: doc.title,
    date: doc.uploaded_at,
    fileName: doc.file_name,
    status: doc.status,
  };
}

const mockDataService: DatasetService = {
  // ---- appDb: users / profile ----
  async getCurrentUser() {
    await delay();
    return clone(data.appDb.users[0]);
  },

  async getPatientProfile(userId) {
    await delay();
    const p = data.appDb.patient_profiles.find((p) => p.user_id === userId);
    return p ? clone(p) : null;
  },

  // ---- appDb: institutions & connections ----
  async getInstitutions() {
    await delay();
    return clone(data.appDb.institutions);
  },

  async getConnections(patientId) {
    await delay();
    return clone(
      data.appDb.institution_connections.filter(
        (c) => c.patient_id === patientId
      )
    );
  },

  async connectInstitution(patientId, institutionId) {
    await delay();
    const conn: InstitutionConnection = {
      id: `conn-${Date.now()}`,
      patient_id: patientId,
      institution_id: institutionId,
      origin: 'user_added',
      status: 'pending_consent',
      connected_at: new Date().toISOString(),
    };
    data.appDb.institution_connections.push(conn);
    return clone(conn);
  },

  async revokeConnection(connectionId) {
    await delay();
    const conn = data.appDb.institution_connections.find(
      (c) => c.id === connectionId
    );
    if (conn) conn.status = 'revoked';
    return conn ? clone(conn) : null;
  },

  // ---- appDb: caregivers ----
  async getCaregiverLinks(patientId) {
    await delay();
    return clone(
      data.appDb.caregiver_links.filter((l) => l.patient_id === patientId)
    );
  },

  async getCaregiverPermissions(caregiverLinkId) {
    await delay();
    return clone(
      data.appDb.caregiver_permissions.filter(
        (p) => p.caregiver_link_id === caregiverLinkId
      )
    );
  },

  // ---- appDb: self-uploaded documents ----
  async getDocuments(patientId, category = null) {
    await delay();
    return data.appDb.documents
      .filter((d) => d.patient_id === patientId)
      .map(selfUploadedToRecord)
      .filter((r) => !category || r.category === category);
  },

  async uploadDocument(patientId, input: UploadDocumentInput) {
    await delay();
    const doc: SelfUploadedDocument = {
      id: `doc-${Date.now()}`,
      patient_id: patientId,
      document_type_code: input.documentTypeCode,
      title: input.title,
      file_name: input.fileName,
      status: 'stored',
      uploaded_at: new Date().toISOString(),
    };
    data.appDb.documents.push(doc);
    return selfUploadedToRecord(doc);
  },

  // ---- Combined category page: self-uploaded + live institutional fetch ----
  // This is the one real endpoint replicates faithfully: institutional data
  // is fetched on demand (per §0 of the app schema), never stored.
  async getCategoryRecords(patientId, category) {
    await delay(400); // slightly longer, simulating a live proxy fetch

    const selfRecords = data.appDb.documents
      .filter((d) => d.patient_id === patientId)
      .map(selfUploadedToRecord)
      .filter((r) => r.category === category);

    const activeConnections = data.appDb.institution_connections.filter(
      (c) => c.patient_id === patientId && c.status === 'active'
    );

    const institutionalRecords: MedicalRecord[] = activeConnections.flatMap(
      (conn) => {
        const institution = data.appDb.institutions.find(
          (i) => i.id === conn.institution_id
        );
        if (!institution) return [];
        const collections = data.institutionalData[conn.institution_id] || {};
        return Object.values(collections).flatMap((resources) =>
          resources
            .map((resource) => toRecord(resource, institution))
            .filter((r) => r.category === category)
        );
      }
    );

    return clone([...selfRecords, ...institutionalRecords]);
  },

  // ---- appDb: exports & audit ----
  async getDataExports(patientId) {
    await delay();
    return clone(
      data.appDb.data_exports.filter((e) => e.patient_id === patientId)
    );
  },

  async requestExport(patientId, categories) {
    await delay();
    const exp: DataExport = {
      id: `export-${Date.now()}`,
      patient_id: patientId,
      categories,
      status: 'processing',
      created_at: new Date().toISOString(),
      download_url: null,
    };
    data.appDb.data_exports.push(exp);
    return clone(exp);
  },

  async getAuditLogs(patientId) {
    await delay();
    // audit_logs isn't scoped by patient_id in the sample; filter by actor as a stand-in
    return clone(
      data.appDb.audit_logs.filter((l) => l.actor_user_id === patientId)
    );
  },
};

export default mockDataService;
