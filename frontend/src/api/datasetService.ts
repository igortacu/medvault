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
  UploadDocumentInput,
  OriginalDocumentResponse,
} from './types';

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
    throw new Error(
      `Request failed: ${options.method || 'GET'} ${path} (${res.status})`
    );
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

const realDataService: DatasetService = {
  async getCurrentUser() {
    return request('/users/me');
  },

  async getPatientProfile(userId) {
    return request(`/patients/${userId}/profile`);
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

  async revokeConnection(connectionId) {
    return request(`/v1/institution-connections/${connectionId}`, {
      method: 'DELETE',
    });
  },

  async getCaregiverLinks(patientId) {
    return request(`/patients/${patientId}/caregiver-links`);
  },

  async getCaregiverPermissions(caregiverLinkId) {
    return request(`/caregiver-links/${caregiverLinkId}/permissions`);
  },

  async getDocuments(patientId, category: DataCategory | null = null) {
    const qs = category ? `?category=${encodeURIComponent(category)}` : '';
    return request(`/patients/${patientId}/documents${qs}`);
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
  async getCategoryRecords(patientId, category, filters) {
    const params = new URLSearchParams();

    if (filters?.search) {
      params.set('search', filters.search);
    }

    if (filters?.documentTypeCode) {
      params.set('documentTypeCode', filters.documentTypeCode);
    }

    if (filters?.institutionId) {
      params.set('institutionId', filters.institutionId);
    }

    if (filters?.source) {
      params.set('source', filters.source);
    }

    if (filters?.dateFrom) {
      params.set('dateFrom', filters.dateFrom);
    }

    if (filters?.dateTo) {
      params.set('dateTo', filters.dateTo);
    }

    const queryString = params.toString();

    return request(
      `/patients/${patientId}/categories/${encodeURIComponent(category)}/records${
        queryString ? `?${queryString}` : ''
      }`
    );
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
