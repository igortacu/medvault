// src/types.ts

// ====================
// Common Types
// ====================

export type UUID = string;
export type Timestamp = string;
export type DateString = string;

// ====================
// Users
// ====================

export interface User {
  id: UUID;
  phone_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: DateString;
  mfa_enabled: boolean;
  idnp_encrypted: string;
  idnp_hash: string;
}

// ====================
// Institutions
// ====================

export interface Institution {
  id: UUID;
  name: string;
}

// ====================
// Institution Connections
// ====================

export type InstitutionConnectionStatus = 'active' | 'revoked';

export interface InstitutionConnection {
  id: UUID;
  patient_id: UUID;
  institution_id: UUID;
  status: InstitutionConnectionStatus;
  revoked_at: Timestamp | null;
}

// ====================
// Caregiver Links
// ====================

export type CaregiverLinkStatus = 'active' | 'revoked' | 'pending';

export interface CaregiverLink {
  id: UUID;
  elder_patient_id: UUID;
  caregiver_user_id: UUID;
  status: CaregiverLinkStatus;
}

// ====================
// Caregiver Permissions
// ====================

export type PermissionCategory =
  'diagnostics' | 'prescriptions' | 'certificates' | 'other_medical_info';

export interface CaregiverPermission {
  id: UUID;
  caregiver_link_id: UUID;
  category: PermissionCategory;
  can_view: boolean;
  can_export: boolean;
}

// ====================
// Documents
// ====================

export type DocumentCategory =
  'diagnostic' | 'prescription' | 'certificate' | 'medical_history';

export type DocumentStatus = 'available' | 'archived';

export interface Document {
  id: UUID;
  patient_id: UUID;
  institution_connection_id?: UUID;
  category: DocumentCategory;
  source: string;
  status: DocumentStatus;
  deleted_at: Timestamp | null;
  purge_scheduled_at: Timestamp | null;
}

// ====================
// Diagnostics
// ====================

export interface Diagnostic {
  id: UUID;
  patient_id: UUID;
  document_id: UUID;
  institution_connection_id?: UUID;
  record_date: DateString;
  diagnostic_name: string;
}

// ====================
// prescriptions
// ====================

export type PrescriptionStatus = 'active' | 'completed';

export interface Prescription {
  id: UUID;
  patient_id: UUID;
  document_id: UUID;
  institution_connection_id?: UUID;
  medication_name: string;
  status: PrescriptionStatus;
}

// ====================
// Certificates
// ====================

export interface Certificate {
  id: UUID;
  patient_id: UUID;
  document_id: UUID;
  institution_connection_id?: UUID;
  issue_date: DateString;
  visible_to_caregiver: boolean;
}

// ====================
// Other Medical Information
// ====================

export type MedicalInfoFieldType = 'allergy' | 'blood_type';

export interface OtherMedicalInfo {
  id: UUID;
  patient_id: UUID;
  document_id: UUID;
  institution_connection_id: UUID;
  field_type: MedicalInfoFieldType;
  field_value: string;
}

// ====================
// Data Export Requests
// ====================

export type DataExportScope =
  'all_medical_data' | 'diagnostics' | 'medical_documents';

export type DataExportFormat = 'pdf' | 'json';

export type DataExportStatus =
  'requested' | 'processing' | 'completed' | 'failed';

export interface DataExportRequest {
  id: UUID;
  patient_id: UUID;
  scope: DataExportScope;
  format: DataExportFormat;
  status: DataExportStatus;
}

// ====================
// Verification Codes
// ====================

export type VerificationPurpose = 'login' | 'caregiver_access';

export interface VerificationCode {
  id: UUID;
  user_id: UUID;
  purpose: VerificationPurpose;
  expires_at: Timestamp;
}

// ====================
// Step-Up Verifications
// ====================

export type StepUpAction = 'export_medical_data' | 'view_sensitive_information';

export type VerificationFactor = 'mfa' | 'sms';

export type StepUpVerificationStatus = 'verified' | 'failed';

export interface StepUpVerification {
  id: UUID;
  user_id: UUID;
  action: StepUpAction;
  factor_used: VerificationFactor;
  status: StepUpVerificationStatus;
}

// ====================
// Audit Logs
// ====================

export type AuditAction =
  | 'viewed_medical_records'
  | 'viewed_diagnostics'
  | 'export_requested'
  | 'caregiver_permission_updated'
  | 'institution_connected';

export interface AuditLog {
  id: UUID;
  actor_user_id: UUID;
  target_patient_id: UUID;
  action: AuditAction;
  created_at: Timestamp;
}
