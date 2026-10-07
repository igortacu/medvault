// realDataService.ts
// Same interface as mockDataService.ts (both implement DatasetService), but
// backed by the real backend. The backend is responsible for doing exactly
// what §0 of the app schema describes: appDb endpoints hit Postgres,
// getCategoryRecords proxies live to the mock/real institutional API and
// merges it with self-uploaded documents, without ever persisting the
// institutional part.

import type {
  DatasetService,
  DataCategory,
  Institution,
  InstitutionConnection,
  MedicalRecord,
  UploadDocumentInput,
  OriginalDocumentResponse,
} from './types';
import type {
  CaregiverLink,
  CaregiverLinkStatus,
  CaregiverPermission,
} from './caregiver.types';
import { filterRecords, labelForResourceType } from './records';
import { ApiError } from './errors';

// Vite-style env access; adjust if using a different bundler (e.g. process.env for Next/CRA).
const BASE_URL: string =
  (import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_API_BASE_URL || '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  });
  if (!res.ok) {
    throw new ApiError(
      `Request failed: ${options.method || 'GET'} ${path} (${res.status})`,
      res.status
    );
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

// ---- Backend wire shapes (see the backend's /docs) ----

interface BackendCategoryListItem {
  id: string;
  type: string;
  title?: string | null;
  document_date?: string | null;
  specialty?: string | null;
  practitioner_name?: string | null;
  issuer_name?: string | null;
  /** "Self-uploaded", or the institution's name for institutional records. */
  source: string;
  date_added?: string | null;
  original_path: string;
}

interface BackendPatientInfo {
  first_name: string | null;
  last_name: string | null;
  date_of_birth: string | null;
  weight_kg: number | null;
  height_cm: number | null;
}

export interface BackendPermissionItem {
  category: DataCategory;
  can_view: boolean;
  can_view_original: boolean;
  can_export: boolean;
  can_upload: boolean;
}

interface BackendCaregiverLinkItem {
  id: string;
  caregiver_user_id?: string | null;
  status: CaregiverLinkStatus;
  invited_at?: string | null;
  permissions: BackendPermissionItem[];
}

const SELF_UPLOADED_SOURCE = 'Self-uploaded';

/** Backend list route per category; patient_info holds measurements, not documents. */
const CATEGORY_PATHS: Partial<Record<DataCategory, string>> = {
  diagnoses: '/diagnostics',
  prescriptions: '/prescriptions',
  certificates: '/certificates',
  analyses: '/analyses',
  other_med_info: '/other-med-info',
};

export function toCaregiverPermissions(
  linkId: string,
  items: BackendPermissionItem[]
): CaregiverPermission[] {
  return items.map((p) => ({
    caregiver_link_id: linkId,
    category: p.category,
    granted: p.can_view,
  }));
}

// Institutional records only carry the institution's name, so resolve its id
// from the catalogue (fetched once) to support the institutionId filter.
let institutionsByName: Promise<Map<string, string>> | null = null;

function getInstitutionIdsByName(): Promise<Map<string, string>> {
  institutionsByName ??= request<Institution[]>('/v1/institutions')
    .then((list) => new Map(list.map((i) => [i.name, i.id])))
    .catch(() => {
      institutionsByName = null;
      return new Map<string, string>();
    });
  return institutionsByName;
}

function toMedicalRecord(
  item: BackendCategoryListItem,
  category: DataCategory,
  institutionIds: Map<string, string>
): MedicalRecord {
  const selfUploaded = item.source === SELF_UPLOADED_SOURCE;
  // Institutional original_path: /institutions/{slug}/{resourceType}/{id}
  const resourceType = selfUploaded
    ? 'DocumentReference'
    : (item.original_path.split('/')[3] ?? 'DocumentReference');
  return {
    id: item.id,
    source: selfUploaded ? 'self_uploaded' : 'institution',
    sourceLabel: item.source,
    institutionId: selfUploaded ? null : (institutionIds.get(item.source) ?? null),
    category,
    documentTypeCode: item.type,
    resourceType,
    type: labelForResourceType(resourceType),
    title: item.title || item.type,
    date: item.document_date ?? item.date_added ?? null,
  };
}

async function listCategory(
  patientId: string,
  category: DataCategory
): Promise<MedicalRecord[]> {
  const path = CATEGORY_PATHS[category];
  if (!path) return [];
  const [items, institutionIds] = await Promise.all([
    request<BackendCategoryListItem[]>(
      `${path}?patient_id=${encodeURIComponent(patientId)}`
    ),
    getInstitutionIdsByName(),
  ]);
  return items.map((item) => toMedicalRecord(item, category, institutionIds));
}

const realDataService: DatasetService = {
  async login(phone, password) {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ phone, password }),
    });
  },

  async logout() {
    await request<null>('/auth/logout', { method: 'POST' });
  },

  async getCurrentUser() {
    return request('/users/me');
  },

  // The backend doesn't return the IDNP, so idnp stays empty.
  async getPatientProfile(userId) {
    const info = await request<BackendPatientInfo>(
      `/patient-info?patient_id=${encodeURIComponent(userId)}`
    );
    return {
      user_id: userId,
      idnp: '',
      first_name: info.first_name ?? '',
      last_name: info.last_name ?? '',
      birth_date: info.date_of_birth ?? '',
      weight_kg: info.weight_kg ?? 0,
      height_cm: info.height_cm ?? 0,
    };
  },

  async getInstitutions() {
    return request('/v1/institutions');
  },

  async getConnections() {
    return request('/v1/institution-connections');
  },

  async connectInstitution(institutionId, idnp, consentTextVersion) {
    return request(`/v1/institutions/${institutionId}/connect`, {
      method: 'POST',
      body: JSON.stringify({
        idnp,
        consent_text_version: consentTextVersion,
      }),
    });
  },

  // The backend finishes authorization in its own OAuth callback
  // (/v1/institutions/callback); here we only re-read the resulting state.
  async authorizeInstitutionConnection(connectionId) {
    const connections = await request<InstitutionConnection[]>(
      '/v1/institution-connections'
    );
    return connections.find((c) => c.id === connectionId) ?? null;
  },

  async revokeConnection(connectionId) {
    await request<null>(`/v1/institution-connections/${connectionId}`, {
      method: 'DELETE',
    });
  },

  // GET /caregivers lists the signed-in patient's own links.
  async getCaregiverLinks(patientId): Promise<CaregiverLink[]> {
    const links = await request<BackendCaregiverLinkItem[]>('/caregivers');
    return links.map((link) => ({
      id: link.id,
      patient_id: patientId,
      caregiver_user_id: link.caregiver_user_id ?? '',
      status: link.status,
      created_at: link.invited_at ?? '',
    }));
  },

  async getCaregiverPermissions(caregiverLinkId) {
    const links = await request<BackendCaregiverLinkItem[]>('/caregivers');
    const link = links.find((l) => l.id === caregiverLinkId);
    return link ? toCaregiverPermissions(link.id, link.permissions) : [];
  },

  // No dedicated documents route: gather the self-uploaded rows from the
  // category lists.
  async getDocuments(patientId, category: DataCategory | null = null) {
    const categories = category
      ? [category]
      : (Object.keys(CATEGORY_PATHS) as DataCategory[]);
    const lists = await Promise.all(
      categories.map((c) => listCategory(patientId, c))
    );
    return lists.flat().filter((r) => r.source === 'self_uploaded');
  },

  async uploadDocument(patientId, input: UploadDocumentInput) {
    return request(`/patients/${patientId}/documents`, {
      method: 'POST',
      body: JSON.stringify({
        title: input.title,
        document_type_code: input.documentTypeCode,
        file_name: input.fileName,
      }),
    });
  },

  // Backend fetches live from the institutional API for every active
  // connection, merges with self-uploaded docs, and returns one list —
  // nothing institutional is written to Postgres on this call.
  // Nothing institutional is written to Postgres on this call.
  // The backend's own filters (exact source label / date / specialty) don't
  // match MedicalRecordFilters, so filter client-side like the mock does.
  async getCategoryRecords(patientId, category, filters) {
    return filterRecords(await listCategory(patientId, category), filters);
  },

  async getOriginalDocument(documentId): Promise<OriginalDocumentResponse> {
    return request(`/documents/${documentId}/original`);
  },

  async getDataExports(patientId) {
    return request(`/patients/${patientId}/exports`);
  },

  async requestExport(patientId, categories) {
    return request(`/patients/${patientId}/exports`, {
      method: 'POST',
      body: JSON.stringify({ categories }),
    });
  },

  async getAuditLogs(patientId) {
    return request(`/patients/${patientId}/audit-logs`);
  },
};

export default realDataService;
