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
  CategoryResult,
  UploadDocumentInput,
  DataExport,
  MedicalRecordFilters,
} from './types';

import { filterRecords } from './records';
import { ApiError, RateLimited } from './errors';

const data = seed as unknown as SeedData;

const MIME_TYPES_BY_EXTENSION: Record<string, string> = {
  pdf: 'application/pdf',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
};

function mimeTypeForFileName(fileName: string): string {
  const extension = fileName.split('.').pop()?.toLowerCase() ?? '';
  return MIME_TYPES_BY_EXTENSION[extension] ?? 'application/octet-stream';
}

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const delay = (ms = 250): Promise<void> =>
  new Promise((res) => setTimeout(res, ms));

function categoryForCode(code: string | null): DataCategory | null {
  if (!code) return null;
  const dt = data.appDb.document_types.find((d) => d.code === code);
  return dt ? dt.category : null;
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
    title:
      resource.code?.text ||
      resource.medicationCodeableConcept?.text ||
      (typeof resource.conclusion === 'string' ? resource.conclusion : null) ||
      code ||
      resource.resourceType,
    date:
      resource.effectiveDateTime ||
      resource.recordedDate ||
      resource.authoredOn ||
      resource.period?.start ||
      null,
    raw: resource,
    originalRef: `institution:${institution.id}/${resource.resourceType}/${resource.id}`,
    hasOriginal: RESOURCES_WITH_ORIGINALS.has(resource.resourceType),
  };
}

// The resource types institutions attach a scanned original to.
const RESOURCES_WITH_ORIGINALS = new Set([
  'DocumentReference',
  'DiagnosticReport',
  'MedicationRequest',
]);

const EXPORT_WINDOW_MS = 30 * 60 * 1000;
const mockExports = new Map<string, DataExport[]>();

// The seed's exports predate the current shape and are long past their
// 30-minute window, so they start out expired.
function exportsFor(patientId: string): DataExport[] {
  if (!mockExports.has(patientId)) {
    const seeded = (
      data.appDb.data_exports as unknown as {
        id: string;
        patient_id: string;
        categories: DataExport['categories'];
        created_at: string;
      }[]
    )
      .filter((e) => e.patient_id === patientId)
      .map<DataExport>((e) => ({
        id: e.id,
        categories: e.categories,
        status: 'expired',
        format: 'pdf',
        single_record: false,
        created_at: e.created_at,
        completed_at: e.created_at,
        expires_at: e.created_at,
        download_url: null,
      }))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    mockExports.set(patientId, seeded);
  }
  return mockExports.get(patientId)!;
}

function withExpiry(exp: DataExport): DataExport {
  const expired =
    exp.status === 'ready' &&
    exp.expires_at !== null &&
    Date.parse(exp.expires_at) <= Date.now();
  return expired
    ? { ...exp, status: 'expired', download_url: null }
    : { ...exp };
}

/** A one-page sample PDF standing in for an institution's original file. */
function samplePdf(title: string): Blob {
  const text = `SAMPLE - ${title}`.replace(/[^\x20-\x7e]/g, '?').slice(0, 80);
  const escaped = text.replace(/[\\()]/g, (c) => `\\${c}`);
  const stream = `BT /F1 14 Tf 60 760 Td (${escaped}) Tj 0 -24 Td (Mock mode: no real institution was contacted.) Tj ET`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  let pdf = '%PDF-1.4\n';
  const offsets = objects.map((body, i) => {
    const offset = pdf.length;
    pdf += `${i + 1} 0 obj\n${body}\nendobj\n`;
    return offset;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets
    .map((o) => `${String(o).padStart(10, '0')} 00000 n \n`)
    .join('');
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new Blob([pdf], { type: 'application/pdf' });
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
    title: doc.title,
    date: doc.uploaded_at,
    fileName: doc.file_name,
    mimeType: doc.mime_type,
    status: doc.status,
  };
}

// The mock "institution" knows every IDNP except this one, so the no-match
// state can be tried in mock mode.
export const MOCK_UNKNOWN_IDNP = '0000000000000';
// Connecting with this IDNP answers 429, so the cooldown can be tried in mock mode.
export const MOCK_RATE_LIMITED_IDNP = '9999999999999';
const MOCK_CONNECT_RETRY_AFTER = 20 * 60;

function mockRateLimit(idnp: string) {
  if (idnp === MOCK_RATE_LIMITED_IDNP) {
    throw new RateLimited(MOCK_CONNECT_RETRY_AFTER);
  }
}

function mockConnect(
  institutionId: string,
  idnp: string,
  consentTextVersion: string
): InstitutionConnection {
  const now = new Date().toISOString();
  const matched = idnp !== MOCK_UNKNOWN_IDNP;
  const conn: InstitutionConnection = {
    id: `conn-${Date.now()}-${institutionId}`,
    patient_id: data.appDb.users[0].id,
    institution_id: institutionId,
    origin:
      data.appDb.institutions.find((i) => i.id === institutionId)?.type ===
      'public'
        ? 'auto_public'
        : 'user_added',
    status: matched ? 'active' : 'no_match',
    connected_at: matched ? now : null,
    granted_scopes: matched
      ? ['patient/Patient.read', 'patient/Observation.read', 'offline_access']
      : null,
    failure_reason: matched ? null : 'access_denied',
    consented_at: now,
    created_at: now,
  };
  void consentTextVersion;
  data.appDb.institution_connections.push(conn);
  return conn;
}

const mockDataService: DatasetService = {
  // ---- appDb: users / profile ----
  async logout() {
    await delay();
  },

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

  async getConnections() {
    await delay();
    const userId = data.appDb.users[0].id;
    return clone(
      data.appDb.institution_connections
        .filter((c) => c.patient_id === userId)
        .sort((a, b) =>
          (b.created_at ?? b.connected_at ?? '').localeCompare(
            a.created_at ?? a.connected_at ?? ''
          )
        )
    );
  },

  // There is no institution to redirect to, so the OAuth round trip resolves
  // at once and the "authorize URL" lands straight back on the page.
  async connectInstitution(institutionId, idnp, consentTextVersion) {
    await delay();
    mockRateLimit(idnp);
    const conn = mockConnect(institutionId, idnp, consentTextVersion);
    return {
      connection_id: conn.id,
      authorize_url: `/institutions?connection=${conn.status}`,
    };
  },

  async connectPublicInstitutions(idnp, institutionIds, consentTextVersion) {
    const chosen = new Set(institutionIds);
    await delay(600);
    mockRateLimit(idnp);
    const connected = new Set(
      data.appDb.institution_connections
        .filter(
          (c) =>
            c.patient_id === data.appDb.users[0].id &&
            ['authorizing', 'active'].includes(c.status)
        )
        .map((c) => c.institution_id)
    );
    const attempts = data.appDb.institutions
      .filter(
        (i) => i.type === 'public' && chosen.has(i.id) && !connected.has(i.id)
      )
      .map((i) => mockConnect(i.id, idnp, consentTextVersion));
    return {
      authorize_url: attempts.length ? '/institutions?connection=done' : null,
      connections: attempts.map((c) => ({
        connection_id: c.id,
        institution_id: c.institution_id,
        status: c.status,
      })),
    };
  },
  async authorizeInstitutionConnection(connectionId) {
    await delay();

    const conn = data.appDb.institution_connections.find(
      (c) => c.id === connectionId
    );

    if (!conn) return null;

    conn.status = 'active';

    return clone(conn);
  },

  async revokeConnection(connectionId) {
    await delay();
    const conn = data.appDb.institution_connections.find(
      (c) => c.id === connectionId
    );
    if (conn) {
      conn.status = 'revoked';
      conn.revoked_at = new Date().toISOString();
    }
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
      mime_type: mimeTypeForFileName(input.fileName),
      file_url: `/mock-documents/${input.fileName}`,
      status: 'stored',
      uploaded_at: new Date().toISOString(),
    };
    data.appDb.documents.push(doc);
    return selfUploadedToRecord(doc);
  },

  // ---- Combined category page: self-uploaded + live institutional fetch ----
  // This is the one real endpoint replicates faithfully: institutional data
  // is fetched on demand (per §0 of the app schema), never stored.
  async getCategoryRecords(
    patientId: string,
    category: DataCategory,
    filters?: MedicalRecordFilters
  ): Promise<CategoryResult> {
    await delay(400); // slightly longer, simulating a live proxy fetch

    const selfRecords = data.appDb.documents
      .filter((d) => d.patient_id === patientId)
      .map(selfUploadedToRecord)
      .filter((r) => r.category === category);

    const activeConnections = data.appDb.institution_connections.filter(
      (c) => c.patient_id === patientId && c.status === 'active'
    );
    const idnp = data.appDb.patient_profiles.find(
      (p) => p.user_id === patientId
    )?.idnp;

    const institutionalRecords: MedicalRecord[] = activeConnections.flatMap(
      (conn) => {
        const institution = data.appDb.institutions.find(
          (i) => i.id === conn.institution_id
        );
        if (!institution) return [];
        const collections = data.institutionalData[conn.institution_id] || {};
        // Like the real institution API: only the resources of the FHIR
        // Patient matched by this user's IDNP.
        const fhirPatient = (collections.Patient ?? []).find((p) =>
          (p.identifier as { value?: string }[] | undefined)?.some(
            (id) => id.value === idnp
          )
        );
        if (!fhirPatient) return [];
        const patientRef = `Patient/${fhirPatient.id}`;
        return Object.values(collections).flatMap((resources) =>
          resources
            .filter((resource) => {
              const ref = (resource.subject ?? resource.patient) as
                { reference?: string } | undefined;
              return ref?.reference === patientRef;
            })
            .map((resource) => toRecord(resource, institution))
            .filter((r) => r.category === category)
        );
      }
    );

    return clone({
      records: filterRecords(
        [...selfRecords, ...institutionalRecords],
        filters
      ),
      sources: activeConnections.map((conn) => ({
        institutionId: conn.institution_id,
        institution:
          data.appDb.institutions.find((i) => i.id === conn.institution_id)
            ?.name ?? '',
        status: 'ok' as const,
        count: institutionalRecords.filter(
          (r) => r.institutionId === conn.institution_id
        ).length,
      })),
    });
  },

  // ---- Original file retrieval (mirrors GET /documents/{id}/original) ----
  async getOriginalDocument(documentId) {
    await delay();
    const doc = data.appDb.documents.find((d) => d.id === documentId);
    if (!doc) {
      throw new ApiError('You do not have access to this document.', 403);
    }
    if (doc.status !== 'stored') {
      throw new ApiError('The original file is no longer available.', 404);
    }
    const res = await fetch(doc.file_url);
    if (!res.ok) {
      throw new ApiError('The original file is unavailable.', 404);
    }
    return res.blob();
  },

  async getInstitutionalOriginal(record) {
    await delay();
    if (!record.hasOriginal) {
      throw new ApiError('The original file is not available.', 404);
    }
    return samplePdf(record.title);
  },

  // ---- appDb: exports & audit ----
  async getDataExports(patientId) {
    await delay();
    return exportsFor(patientId).map(withExpiry);
  },

  // Ready after a short "generation" delay, downloadable for 30 minutes from
  // an in-memory sample file, like the backend's job.
  async requestExport(patientId, exportRequest) {
    await delay();
    const exp: DataExport = {
      id: `export-${Date.now()}`,
      categories: exportRequest.categories,
      status: 'processing',
      format: exportRequest.format,
      single_record: Boolean(exportRequest.scopeRef),
      created_at: new Date().toISOString(),
      completed_at: null,
      expires_at: null,
      download_url: null,
    };
    exportsFor(patientId).unshift(exp);
    setTimeout(() => {
      const now = Date.now();
      exp.status = 'ready';
      exp.completed_at = new Date(now).toISOString();
      exp.expires_at = new Date(now + EXPORT_WINDOW_MS).toISOString();
      exp.download_url = URL.createObjectURL(
        exp.format === 'pdf'
          ? samplePdf(`MedVault export (${exp.categories.join(', ')})`)
          : new Blob(
              [JSON.stringify({ format: 'medvault-export/1', mock: true })],
              { type: 'application/json' }
            )
      );
    }, 1500);
    return clone(exp);
  },

  exportFileUrl(dataExport) {
    return dataExport.download_url ?? '';
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
