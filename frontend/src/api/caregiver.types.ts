import type { DataCategory } from './types';

export type CaregiverLinkStatus = 'pending' | 'active' | 'rejected' | 'revoked';

export type CaregiverLink = {
  id: string;
  patient_id: string;
  caregiver_user_id: string;
  status: CaregiverLinkStatus;
  created_at: string;
};

export type CaregiverPermission = {
  caregiver_link_id: string;
  category: DataCategory;
  granted: boolean;
};

export type Caregiver = {
  linkId: string;
  userId: string;
  name: string;
  phone: string;
  status: CaregiverLinkStatus;
  permissions: CaregiverPermission[];
};

export type CareRecipient = {
  linkId: string;
  patientId: string;
  name: string;
  /** Optional — Avatar falls back to initials when absent. */
  photoUrl?: string;
  phone: string;
  birthDate?: string;
  /** When the caregiver link was created. */
  since: string;
  status: CaregiverLinkStatus;
  permissions: CaregiverPermission[];
};

export type InviteCaregiverRequest = {
  patientId: string;
  caregiverUserId: string;
  permissions: DataCategory[];
};
export type UpdateCaregiverPermissionsRequest = {
  linkId: string;
  permissions: DataCategory[];
};
export type RespondToCaregiverRequest = {
  linkId: string;
  accept: boolean;
};

export type CaregiverCandidate = {
  userId: string;
  firstName: string;
  lastName: string;
  birthDate: string;
};

/** The interface both mockCaregiverService and caregiverService implement. */
export interface CaregiverService {
  /** People who have been granted access to this patient's data. */
  getUsersWithAccess(patientId: string): Promise<Caregiver[]>;
  /** Patients this user has caregiver access to. */
  getUsersICareFor(caregiverUserId: string): Promise<CareRecipient[]>;

  /** Resolves a phone number to the account it belongs to, if any. */
  findUserByPhone(phone: string): Promise<CaregiverCandidate | null>;

  inviteCaregiver(request: InviteCaregiverRequest): Promise<Caregiver>;
  updateCaregiverPermissions(
    request: UpdateCaregiverPermissionsRequest
  ): Promise<Caregiver>;
  respondToCaregiverRequest(
    request: RespondToCaregiverRequest
  ): Promise<CareRecipient>;
  revokeCaregiverLink(linkId: string): Promise<void>;
}
