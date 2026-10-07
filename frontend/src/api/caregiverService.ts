// caregiverService.ts
// Same interface as mockCaregiverService.ts (both implement CaregiverService),
// but backed by the real backend.

import type {
  CareRecipient,
  Caregiver,
  CaregiverLinkStatus,
  CaregiverService,
} from './caregiver.types';
import type { DataCategory } from './types';
import { toCaregiverPermissions } from './datasetService';
import type { BackendPermissionItem } from './datasetService';
import { ApiError } from './errors';

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

interface BackendCaregiverLinkItem {
  id: string;
  caregiver_user_id?: string | null;
  first_name: string;
  last_name: string;
  phone: string;
  status: CaregiverLinkStatus;
  permissions: BackendPermissionItem[];
}

interface BackendCaredPatientItem {
  link_id: string;
  patient_user_id: string;
  status: CaregiverLinkStatus;
  since?: string | null;
  permissions: BackendPermissionItem[];
}

interface BackendPatientBasics {
  first_name: string | null;
  last_name: string | null;
  date_of_birth: string | null;
}

const ALL_CATEGORIES: DataCategory[] = [
  'diagnoses',
  'certificates',
  'analyses',
  'prescriptions',
  'patient_info',
  'other_med_info',
];

function toCaregiver(link: BackendCaregiverLinkItem): Caregiver {
  return {
    linkId: link.id,
    userId: link.caregiver_user_id ?? '',
    name: `${link.first_name} ${link.last_name}`.trim(),
    phone: link.phone,
    status: link.status,
    permissions: toCaregiverPermissions(link.id, link.permissions),
  };
}

async function getCaregiver(linkId: string): Promise<Caregiver> {
  const links = await request<BackendCaregiverLinkItem[]>('/caregivers');
  const link = links.find((l) => l.id === linkId);
  if (!link) throw new Error(`Caregiver link ${linkId} not found`);
  return toCaregiver(link);
}

// /caregivers/patients has no names, so read each patient's basics (a
// caregiver may read them, see migration 0008). The phone isn't exposed.
async function toCareRecipient(
  item: BackendCaredPatientItem
): Promise<CareRecipient> {
  const basics = await request<BackendPatientBasics>(
    `/patient-info?patient_id=${encodeURIComponent(item.patient_user_id)}`
  ).catch(() => null);
  return {
    linkId: item.link_id,
    patientId: item.patient_user_id,
    name: `${basics?.first_name ?? ''} ${basics?.last_name ?? ''}`.trim(),
    phone: '',
    birthDate: basics?.date_of_birth ?? undefined,
    since: item.since ?? '',
    status: item.status,
    permissions: toCaregiverPermissions(item.link_id, item.permissions),
  };
}

const caregiverService: CaregiverService = {
  // Both lists are scoped to the signed-in user by the backend, so the
  // id arguments are ignored.
  async getUsersWithAccess() {
    const links = await request<BackendCaregiverLinkItem[]>('/caregivers');
    return links.map(toCaregiver);
  },

  async getUsersICareFor() {
    const items = await request<BackendCaredPatientItem[]>(
      '/caregivers/patients'
    );
    return Promise.all(items.map(toCareRecipient));
  },

  async findUserByPhone(phone) {
    return request(`/users/lookup?phone=${encodeURIComponent(phone)}`);
  },

  async inviteCaregiver(request_) {
    return request(`/patients/${request_.patientId}/caregivers`, {
      method: 'POST',
      body: JSON.stringify({
        caregiver_user_id: request_.caregiverUserId,
        permissions: request_.permissions,
      }),
    });
  },

  // The UI grants view access per category; send every category so the
  // unchecked ones are revoked.
  async updateCaregiverPermissions(request_) {
    await request(`/caregivers/links/${request_.linkId}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({
        permissions: ALL_CATEGORIES.map((category) => ({
          category,
          can_view: request_.permissions.includes(category),
        })),
      }),
    });
    return getCaregiver(request_.linkId);
  },

  async respondToCaregiverRequest(request_) {
    const action = request_.accept ? 'accept' : 'reject';
    const result = await request<{ id: string; status: CaregiverLinkStatus }>(
      `/caregivers/links/${request_.linkId}/${action}`,
      { method: 'POST' }
    );
    // Only active links come back from /caregivers/patients.
    const items = await request<BackendCaredPatientItem[]>(
      '/caregivers/patients'
    );
    const item = items.find((i) => i.link_id === request_.linkId);
    if (item) return toCareRecipient(item);
    return {
      linkId: result.id,
      patientId: '',
      name: '',
      phone: '',
      since: '',
      status: result.status,
      permissions: [],
    };
  },

  async revokeCaregiverLink(linkId) {
    await request(`/caregivers/links/${linkId}/revoke`, { method: 'POST' });
  },
};

export default caregiverService;
