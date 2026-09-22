// caregiverService.ts
// Same interface as mockCaregiverService.ts (both implement CaregiverService),
// but backed by the real backend.

import type { CaregiverService } from './caregiver.types';

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

const caregiverService: CaregiverService = {
  async getUsersWithAccess(patientId) {
    return request(`/patients/${patientId}/caregivers`);
  },

  async getUsersICareFor(caregiverUserId) {
    return request(`/users/${caregiverUserId}/care-recipients`);
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

  async updateCaregiverPermissions(request_) {
    return request(`/caregiver-links/${request_.linkId}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({ permissions: request_.permissions }),
    });
  },

  async revokeCaregiverLink(linkId) {
    await request(`/caregiver-links/${linkId}/revoke`, { method: 'POST' });
  },
};

export default caregiverService;
