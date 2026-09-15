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

const BASE_URL = '/api/v1';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const medVaultService = {
  // Authentication

  signUp(data: {
    phone_number: string;
    first_name: string;
    last_name: string;
    date_of_birth: string;
    password: string;
  }): Promise<User> {
    return request<User>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  verifyPhone(phoneNumber: string, code: string): Promise<void> {
    return request<void>('/auth/verify-phone', {
      method: 'POST',
      body: JSON.stringify({
        phone_number: phoneNumber,
        code,
      }),
    });
  },

  signIn(data: { phone_number: string; password: string }): Promise<User> {
    return request<User>('/auth/signin', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  logout(): Promise<void> {
    return request<void>('/auth/logout', {
      method: 'POST',
    });
  },

  requestPasswordReset(phoneNumber: string): Promise<void> {
    return request<void>('/auth/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({
        phone_number: phoneNumber,
      }),
    });
  },

  resetPassword(
    phoneNumber: string,
    code: string,
    newPassword: string
  ): Promise<void> {
    return request<void>('/auth/password-reset', {
      method: 'POST',
      body: JSON.stringify({
        phone_number: phoneNumber,
        code,
        new_password: newPassword,
      }),
    });
  },

  // Patient

  getUser(userId: string): Promise<User> {
    return request<User>(`/users/${userId}`);
  },

  // Medical documents

  getDiagnostics(patientId: string): Promise<Diagnostic[]> {
    return request<Diagnostic[]>(`/patients/${patientId}/diagnostics`);
  },

  getDiagnostic(diagnosticId: string): Promise<Diagnostic> {
    return request<Diagnostic>(`/diagnostics/${diagnosticId}`);
  },

  getPrescriptions(patientId: string): Promise<Prescription[]> {
    return request<Prescription[]>(`/patients/${patientId}/prescriptions`);
  },

  getPrescription(prescriptionId: string): Promise<Prescription> {
    return request<Prescription>(`/prescriptions/${prescriptionId}`);
  },

  getCertificates(patientId: string): Promise<Certificate[]> {
    return request<Certificate[]>(`/patients/${patientId}/certificates`);
  },

  getOtherMedicalInfo(patientId: string): Promise<OtherMedicalInfo[]> {
    return request<OtherMedicalInfo[]>(`/patients/${patientId}/medical-info`);
  },

  // Documents

  getDocuments(patientId: string): Promise<Document[]> {
    return request<Document[]>(`/patients/${patientId}/documents`);
  },

  getDocument(documentId: string): Promise<Document> {
    return request<Document>(`/documents/${documentId}`);
  },

  async uploadDocument(
    patientId: string,
    file: File,
    category: Document['category']
  ): Promise<Document> {
    const formData = new FormData();

    formData.append('file', file);
    formData.append('patient_id', patientId);
    formData.append('category', category);

    const response = await fetch(`${BASE_URL}/documents`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return response.json();
  },

  // Institutions

  getInstitutions(): Promise<Institution[]> {
    return request<Institution[]>('/institutions');
  },

  getInstitutionConnections(
    patientId: string
  ): Promise<InstitutionConnection[]> {
    return request<InstitutionConnection[]>(
      `/patients/${patientId}/institution-connections`
    );
  },

  connectInstitution(
    patientId: string,
    institutionId: string
  ): Promise<InstitutionConnection> {
    return request<InstitutionConnection>(
      `/patients/${patientId}/institution-connections`,
      {
        method: 'POST',
        body: JSON.stringify({
          institution_id: institutionId,
        }),
      }
    );
  },

  revokeInstitutionConnection(connectionId: string): Promise<void> {
    return request<void>(`/institution-connections/${connectionId}`, {
      method: 'DELETE',
    });
  },

  // Caregivers

  getCaregiverLinks(patientId: string): Promise<CaregiverLink[]> {
    return request<CaregiverLink[]>(`/patients/${patientId}/caregivers`);
  },

  getCaregiverPermissions(
    caregiverLinkId: string
  ): Promise<CaregiverPermission[]> {
    return request<CaregiverPermission[]>(
      `/caregiver-links/${caregiverLinkId}/permissions`
    );
  },

  grantCaregiverAccess(
    patientId: string,
    caregiverUserId: string
  ): Promise<CaregiverLink> {
    return request<CaregiverLink>(`/patients/${patientId}/caregivers`, {
      method: 'POST',
      body: JSON.stringify({
        caregiver_user_id: caregiverUserId,
      }),
    });
  },

  updateCaregiverPermission(
    permissionId: string,
    canView: boolean,
    canExport: boolean
  ): Promise<CaregiverPermission> {
    return request<CaregiverPermission>(
      `/caregiver-permissions/${permissionId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          can_view: canView,
          can_export: canExport,
        }),
      }
    );
  },

  revokeCaregiverAccess(caregiverLinkId: string): Promise<void> {
    return request<void>(`/caregiver-links/${caregiverLinkId}`, {
      method: 'DELETE',
    });
  },

  // Documents export

  requestDataExport(
    patientId: string,
    scope: DataExportRequest['scope'],
    format: DataExportRequest['format']
  ): Promise<DataExportRequest> {
    return request<DataExportRequest>(`/patients/${patientId}/exports`, {
      method: 'POST',
      body: JSON.stringify({
        scope,
        format,
      }),
    });
  },

  getDataExport(exportRequestId: string): Promise<DataExportRequest> {
    return request<DataExportRequest>(`/exports/${exportRequestId}`);
  },
};
