import { DataCategory } from './types';

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

/** The interface both mockCaregiverService and caregiverService implement. */
export interface CaregiverService {
  /** People who have been granted access to this patient's data. */
  getUsersWithAccess(patientId: string): Promise<Caregiver[]>;
  /** Patients this user has caregiver access to. */
  getUsersICareFor(caregiverUserId: string): Promise<CareRecipient[]>;

  inviteCaregiver(request: InviteCaregiverRequest): Promise<Caregiver>;
  updateCaregiverPermissions(
    request: UpdateCaregiverPermissionsRequest
  ): Promise<Caregiver>;
  revokeCaregiverLink(linkId: string): Promise<void>;
}
