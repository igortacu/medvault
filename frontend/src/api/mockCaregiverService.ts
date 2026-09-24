// mockCaregiverService.ts
// Frontend-only stand-in for the real backend's caregiver endpoints. Reads
// the same seed.json as mockDatasetService.ts and joins caregiver_links +
// caregiver_permissions with users/patient_profiles into the UI-facing
// Caregiver/CareRecipient shapes.

import seed from '../mocks/seed.json';
import type { SeedData, User } from './types';
import type {
  CaregiverService,
  CaregiverLink,
  CaregiverPermission,
  Caregiver,
  CareRecipient,
} from './caregiver.types';

const data = seed as unknown as SeedData;

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const delay = (ms = 250): Promise<void> =>
  new Promise((res) => setTimeout(res, ms));

function nameForUser(user: User | undefined, userId: string): string {
  if (!user) return userId;
  const profile = data.appDb.patient_profiles.find(
    (p) => p.user_id === user.id
  );
  return profile ? `${profile.first_name} ${profile.last_name}` : user.phone;
}

function permissionsForLink(linkId: string): CaregiverPermission[] {
  return clone(
    data.appDb.caregiver_permissions.filter(
      (p) => p.caregiver_link_id === linkId
    )
  );
}

function toCaregiver(link: CaregiverLink): Caregiver {
  const user = data.appDb.users.find((u) => u.id === link.caregiver_user_id);
  return {
    linkId: link.id,
    userId: link.caregiver_user_id,
    name: nameForUser(user, link.caregiver_user_id),
    phone: user?.phone ?? '',
    status: link.status,
    permissions: permissionsForLink(link.id),
  };
}

function toCareRecipient(link: CaregiverLink): CareRecipient {
  const user = data.appDb.users.find((u) => u.id === link.patient_id);
  return {
    linkId: link.id,
    patientId: link.patient_id,
    name: nameForUser(user, link.patient_id),
    status: link.status,
    permissions: permissionsForLink(link.id),
  };
}

const mockCaregiverService: CaregiverService = {
  async getUsersWithAccess(patientId) {
    await delay();
    return data.appDb.caregiver_links
      .filter((l) => l.patient_id === patientId)
      .map(toCaregiver);
  },

  async getUsersICareFor(caregiverUserId) {
    await delay();
    return data.appDb.caregiver_links
      .filter((l) => l.caregiver_user_id === caregiverUserId)
      .map(toCareRecipient);
  },

  async findUserByPhone(phone) {
    await delay();
    const user = data.appDb.users.find((u) => u.phone === phone);
    if (!user) return null;
    const profile = data.appDb.patient_profiles.find(
      (p) => p.user_id === user.id
    );
    if (!profile) return null;
    return {
      userId: user.id,
      firstName: profile.first_name,
      lastName: profile.last_name,
      birthDate: profile.birth_date,
    };
  },

  async inviteCaregiver(request) {
    await delay();
    const link: CaregiverLink = {
      id: `link-${Date.now()}`,
      patient_id: request.patientId,
      caregiver_user_id: request.caregiverUserId,
      status: 'pending',
      created_at: new Date().toISOString(),
    };
    data.appDb.caregiver_links.push(link);
    request.permissions.forEach((category) => {
      data.appDb.caregiver_permissions.push({
        caregiver_link_id: link.id,
        category,
        granted: true,
      });
    });
    return toCaregiver(link);
  },

  async updateCaregiverPermissions(request) {
    await delay();
    const link = data.appDb.caregiver_links.find(
      (l) => l.id === request.linkId
    );
    if (!link) {
      throw new Error('Caregiver link not found.');
    }
    data.appDb.caregiver_permissions = data.appDb.caregiver_permissions.filter(
      (p) => p.caregiver_link_id !== request.linkId
    );
    request.permissions.forEach((category) => {
      data.appDb.caregiver_permissions.push({
        caregiver_link_id: request.linkId,
        category,
        granted: true,
      });
    });
    return toCaregiver(link);
  },

  async respondToCaregiverRequest({ linkId, accept }) {
    await delay();
    const link = data.appDb.caregiver_links.find((l) => l.id === linkId);
    if (!link) {
      throw new Error('Caregiver request not found.');
    }
    link.status = accept ? 'active' : 'rejected';
    return toCareRecipient(link);
  },

  async revokeCaregiverLink(linkId) {
    await delay();
    const link = data.appDb.caregiver_links.find((l) => l.id === linkId);
    if (link) link.status = 'revoked';
  },
};

export default mockCaregiverService;
