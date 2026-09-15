import type {
  User,
  Institution,
  InstitutionConnection,
  CaregiverLink,
  CaregiverPermission,
  Document,
  Diagnostic,
  Prescription,
  Certificate,
  OtherMedicalInfo,
  DataExportRequest,
} from './types';

import data from '../mocks/seed.json';

const delay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

export const mockMedVaultService = {
  // ─── Authentication ─────────────────────────────────────────────

  async signUp(user: User): Promise<User> {
    await delay();

    return user;
  },

  async verifyPhone(_phoneNumber: string, _code: string): Promise<void> {
    await delay();
  },

  async signIn(phoneNumber: string, _password: string): Promise<User> {
    await delay();

    const user = data.users.find((user) => user.phone_number === phoneNumber);

    if (!user) {
      throw new Error('User not found');
    }

    return user as User;
  },

  async logout(): Promise<void> {
    await delay();
  },

  async requestPasswordReset(_phoneNumber: string): Promise<void> {
    await delay();
  },

  async resetPassword(
    _phoneNumber: string,
    _code: string,
    _newPassword: string
  ): Promise<void> {
    await delay();
  },

  // ─── Patient ────────────────────────────────────────────────────

  async getUser(userId: string): Promise<User> {
    await delay();

    const user = data.users.find((user) => user.id === userId);

    if (!user) {
      throw new Error('User not found');
    }

    return user as User;
  },

  // ─── Medical documents ───────────────────────────────────────────────

  async getDiagnostics(patientId: string): Promise<Diagnostic[]> {
    await delay();

    return data.diagnostics.filter(
      (diagnostic) => diagnostic.patient_id === patientId
    ) as Diagnostic[];
  },

  async getDiagnostic(diagnosticId: string): Promise<Diagnostic> {
    await delay();

    const diagnostic = data.diagnostics.find(
      (diagnostic) => diagnostic.id === diagnosticId
    );

    if (!diagnostic) {
      throw new Error('Diagnostic not found');
    }

    return diagnostic as Diagnostic;
  },

  async getPrescriptions(patientId: string): Promise<Prescription[]> {
    await delay();

    return data.prescriptions.filter(
      (prescription) => prescription.patient_id === patientId
    ) as Prescription[];
  },

  async getPrescription(prescriptionId: string): Promise<Prescription> {
    await delay();

    const prescription = data.prescriptions.find(
      (prescription) => prescription.id === prescriptionId
    );

    if (!prescription) {
      throw new Error('Prescription not found');
    }

    return prescription as Prescription;
  },

  async getCertificates(patientId: string): Promise<Certificate[]> {
    await delay();

    return data.certificates.filter(
      (certificate) => certificate.patient_id === patientId
    ) as Certificate[];
  },

  async getOtherMedicalInfo(patientId: string): Promise<OtherMedicalInfo[]> {
    await delay();

    return data.other_medical_info.filter(
      (info) => info.patient_id === patientId
    ) as OtherMedicalInfo[];
  },

  // ─── Documents ──────────────────────────────────────────────────

  async getDocuments(patientId: string): Promise<Document[]> {
    await delay();

    return data.documents.filter(
      (document) => document.patient_id === patientId
    ) as Document[];
  },

  async getDocument(documentId: string): Promise<Document> {
    await delay();

    const document = data.documents.find(
      (document) => document.id === documentId
    );

    if (!document) {
      throw new Error('Document not found');
    }

    return document as Document;
  },

  async uploadDocument(
    patientId: string,
    file: File,
    category: Document['category']
  ): Promise<Document> {
    await delay(700);

    const document: Document = {
      id: crypto.randomUUID(),
      patient_id: patientId,
      institution_connection_id: undefined,
      category,
      source: 'user_upload',
      status: 'available',
      deleted_at: null,
      purge_scheduled_at: null,
    };

    console.log('Mock uploaded file:', file.name);

    return document;
  },

  // ─── Institutions ───────────────────────────────────────────────

  async getInstitutions(): Promise<Institution[]> {
    await delay();

    return data.institutions as Institution[];
  },

  async getInstitutionConnections(
    patientId: string
  ): Promise<InstitutionConnection[]> {
    await delay();

    return data.institution_connections.filter(
      (connection) => connection.patient_id === patientId
    ) as InstitutionConnection[];
  },

  async connectInstitution(
    patientId: string,
    institutionId: string
  ): Promise<InstitutionConnection> {
    await delay();

    return {
      id: crypto.randomUUID(),
      patient_id: patientId,
      institution_id: institutionId,
      status: 'active',
      revoked_at: null,
    };
  },

  async revokeInstitutionConnection(connectionId: string): Promise<void> {
    await delay();

    console.log('Mock revoked connection:', connectionId);
  },

  // ─── Caregivers ─────────────────────────────────────────────────

  async getCaregiverLinks(patientId: string): Promise<CaregiverLink[]> {
    await delay();

    return data.caregiver_links.filter(
      (link) => link.elder_patient_id === patientId
    ) as CaregiverLink[];
  },

  async getCaregiverPermissions(
    caregiverLinkId: string
  ): Promise<CaregiverPermission[]> {
    await delay();

    return data.caregiver_permissions.filter(
      (permission) => permission.caregiver_link_id === caregiverLinkId
    ) as CaregiverPermission[];
  },

  async grantCaregiverAccess(
    patientId: string,
    caregiverUserId: string
  ): Promise<CaregiverLink> {
    await delay();

    return {
      id: crypto.randomUUID(),
      elder_patient_id: patientId,
      caregiver_user_id: caregiverUserId,
      status: 'active',
    };
  },

  async updateCaregiverPermission(
    permissionId: string,
    canView: boolean,
    canExport: boolean
  ): Promise<CaregiverPermission> {
    await delay();

    const permission = data.caregiver_permissions.find(
      (permission) => permission.id === permissionId
    );

    if (!permission) {
      throw new Error('Permission not found');
    }

    return {
      ...permission,
      can_view: canView,
      can_export: canExport,
    } as CaregiverPermission;
  },

  async revokeCaregiverAccess(caregiverLinkId: string): Promise<void> {
    await delay();

    console.log('Mock revoked caregiver:', caregiverLinkId);
  },

  // ─── Documents export ────────────────────────────────────────────────

  async requestDataExport(
    patientId: string,
    scope: DataExportRequest['scope'],
    format: DataExportRequest['format']
  ): Promise<DataExportRequest> {
    await delay(700);

    return {
      id: crypto.randomUUID(),
      patient_id: patientId,
      scope,
      format,
      status: 'processing',
    };
  },

  async getDataExport(exportRequestId: string): Promise<DataExportRequest> {
    await delay();

    return {
      id: exportRequestId,
      patient_id: 'mock-patient',
      scope: 'all_medical_data',
      format: 'pdf',
      status: 'completed',
    };
  },
};
