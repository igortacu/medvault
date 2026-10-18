// types.ts
// Shared types for both mockDataService.ts and realDataService.ts, so the
// two stay interchangeable at the type level, not just by convention.

import type { CaregiverLink, CaregiverPermission } from './caregiver.types';

export type DataCategory =
  | 'diagnoses'
  | 'certificates'
  | 'analyses'
  | 'prescriptions'
  | 'patient_info'
  | 'other_med_info';

export type UserStatus =
  'pending_verification' | 'active' | 'locked' | 'disabled';
export type InstitutionType = 'public' | 'private';
export type ConnectionOrigin = 'auto_public' | 'user_added';
export type ConnectionStatus =
  | 'pending_consent'
  | 'authorizing'
  | 'active'
  | 'no_match'
  | 'revoked'
  | 'expired'
  | 'error';
export type CaregiverLinkStatus = 'pending' | 'active' | 'rejected' | 'revoked';
export type DocumentStatus = 'stored' | 'rejected';
export type ExportStatus = 'processing' | 'ready' | 'failed';

export interface DocumentTypeDef {
  code: string;
  category: DataCategory;
  label: string;
}

export interface User {
  id: string;
  phone: string;
  status: UserStatus;
  created_at: string;
}

export interface PatientProfile {
  user_id: string;
  idnp: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  weight_kg: number;
  height_cm: number;
}

export interface Institution {
  id: string;
  external_id?: string;
  name: string;
  type: InstitutionType;
  city: string | null;
}

export interface InstitutionConnection {
  id: string;
  patient_id?: string;
  institution_id: string;
  origin: ConnectionOrigin;
  status: ConnectionStatus;
  connected_at: string | null;
  revoked_at?: string | null;
  granted_scopes?: string[] | null;
  /** Why an error/no_match/expired connection ended up that way. */
  failure_reason?: string | null;
  consented_at?: string | null;
  last_fetched_at?: string | null;
  created_at?: string;
}

/** Response of POST /v1/institutions/{id}/connect — the browser is then sent
 * to authorize_url to finish the institution's OAuth flow. */
export interface ConnectInstitutionResponse {
  connection_id: string;
  authorize_url: string;
}

/** Response of POST /v1/institutions/connect (every public institution under
 * one consent). authorize_url is null when there was nothing to authorize. */
export interface ConnectPublicInstitutionsResponse {
  authorize_url: string | null;
  connections: {
    connection_id: string;
    institution_id: string;
    status: ConnectionStatus;
  }[];
}

export interface SelfUploadedDocument {
  id: string;
  patient_id: string;
  document_type_code: string;
  title: string;
  file_name: string;
  mime_type: string;
  file_url: string;
  status: DocumentStatus;
  uploaded_at: string;
}

/** Mirrors the real backend's OriginalDocumentResponse (GET /documents/{id}/original). */
export interface OriginalDocumentResponse {
  url: string;
  expires_in_seconds: number;
}

export interface DataExport {
  id: string;
  patient_id: string;
  categories: DataCategory[];
  status: ExportStatus;
  created_at: string;
  download_url: string | null;
}

export interface AuditLog {
  id: string;
  actor_user_id: string;
  action: string;
  target: string;
  created_at: string;
}

/** A raw FHIR-ish resource as stored/returned by the mock institutional API. */
export interface FhirResource {
  resourceType: string;
  id: string;
  meta?: { source?: string };
  category?: { coding: { system: string; code: string }[] };
  code?: { text?: string };
  medicationCodeableConcept?: { text?: string };
  effectiveDateTime?: string;
  recordedDate?: string;
  authoredOn?: string;
  period?: { start?: string; end?: string };
  [key: string]: unknown;
}

export type InstitutionCollections = Record<string, FhirResource[]>;

export interface SeedData {
  appDb: {
    document_types: DocumentTypeDef[];
    users: User[];
    patient_profiles: PatientProfile[];
    institutions: Institution[];
    institution_connections: InstitutionConnection[];
    caregiver_links: CaregiverLink[];
    caregiver_permissions: CaregiverPermission[];
    documents: SelfUploadedDocument[];
    data_exports: DataExport[];
    audit_logs: AuditLog[];
  };
  institutionalData: Record<string, InstitutionCollections>;
}

/**
 * Human-readable label for each raw resourceType a record can carry — the
 * FHIR resource types returned by institutions, plus the synthetic
 * 'DocumentReference' resourceType used for self-uploaded documents. Shown
 * as the record's "type" on document cards and in the detail modal, since
 * DataCategory alone is too coarse (e.g. 'analyses' covers both a lab
 * Observation and an imaging DiagnosticReport).
 */
export interface ResourceTypeLabelMap {
  Patient: string;
  Condition: string;
  Observation: string;
  DiagnosticReport: string;
  MedicationRequest: string;
  AllergyIntolerance: string;
  Encounter: string;
  DocumentReference: string;
}

/** Unified shape returned to the UI, regardless of where a record came from. */
export interface MedicalRecord {
  id: string;
  source: 'self_uploaded' | 'institution';
  sourceLabel: string;
  institutionId: string | null;
  category: DataCategory | null;
  documentTypeCode: string | null;
  resourceType: string;
  /** Human-readable label for resourceType, e.g. "Lab result". */
  type: string;
  title: string;
  date: string | null;
  fileName?: string;
  mimeType?: string;
  status?: DocumentStatus;
  raw?: FhirResource;
}

/** How one connected institution answered a live category fetch. */
export type SourceState =
  'ok' | 'timeout' | 'unauthorised' | 'unavailable' | 'needs_reconnect';

export interface SourceStatus {
  institutionId: string;
  institution: string;
  status: SourceState;
  count: number;
}

export interface CategoryResult {
  records: MedicalRecord[];
  /** One entry per active connection consulted (empty without connections). */
  sources: SourceStatus[];
}

export interface UploadDocumentInput {
  title: string;
  documentTypeCode: string;
  fileName: string;
}
export interface MedicalRecordFilters {
  search?: string;
  documentTypeCode?: string;
  institutionId?: string;
  source?: 'self_uploaded' | 'institution';
  dateFrom?: string;
  dateTo?: string;
}

/** The interface both mockDataService and realDataService implement. */
export interface DatasetService {
  logout(): Promise<void>;
  getCurrentUser(): Promise<User>;
  getPatientProfile(userId: string): Promise<PatientProfile | null>;

  getInstitutions(): Promise<Institution[]>;
  getConnections(): Promise<InstitutionConnection[]>;
  connectInstitution(
    institutionId: string,
    idnp: string,
    consentTextVersion: string
  ): Promise<ConnectInstitutionResponse>;
  connectPublicInstitutions(
    idnp: string,
    institutionIds: string[],
    consentTextVersion: string
  ): Promise<ConnectPublicInstitutionsResponse>;
  authorizeInstitutionConnection(
    connectionId: string
  ): Promise<InstitutionConnection | null>;
  revokeConnection(connectionId: string): Promise<void>;

  getCaregiverLinks(patientId: string): Promise<CaregiverLink[]>;
  getCaregiverPermissions(
    caregiverLinkId: string
  ): Promise<CaregiverPermission[]>;

  getDocuments(
    patientId: string,
    category?: DataCategory | null
  ): Promise<MedicalRecord[]>;
  uploadDocument(
    patientId: string,
    input: UploadDocumentInput
  ): Promise<MedicalRecord>;

  getCategoryRecords(
    patientId: string,
    category: DataCategory,
    filters?: MedicalRecordFilters
  ): Promise<CategoryResult>;

  getOriginalDocument(documentId: string): Promise<OriginalDocumentResponse>;

  getDataExports(patientId: string): Promise<DataExport[]>;
  requestExport(
    patientId: string,
    categories: DataCategory[]
  ): Promise<DataExport>;

  getAuditLogs(patientId: string): Promise<AuditLog[]>;
}
