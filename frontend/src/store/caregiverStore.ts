import { create } from 'zustand';
import type {
  Caregiver,
  CaregiverCandidate,
  CareRecipient,
  InviteCaregiverRequest,
  RespondToCaregiverRequest,
  UpdateCaregiverPermissionsRequest,
} from '../api/caregiver.types';
import { caregiverApi } from '../api';

interface CaregiverState {
  usersWithAccess: Caregiver[];
  usersICareFor: CareRecipient[];

  isLoading: boolean;
  error: string | null;

  loadUsersWithAccess: (patientId: string) => Promise<void>;
  loadUsersICareFor: (caregiverUserId: string) => Promise<void>;

  findUserByPhone: (phone: string) => Promise<CaregiverCandidate | null>;
  inviteCaregiver: (request: InviteCaregiverRequest) => Promise<void>;
  updateCaregiverPermissions: (
    request: UpdateCaregiverPermissionsRequest
  ) => Promise<void>;
  respondToCaregiverRequest: (
    request: RespondToCaregiverRequest
  ) => Promise<void>;
  revokeCaregiverLink: (linkId: string) => Promise<void>;
}

export const useCaregiverStore = create<CaregiverState>((set, get) => ({
  usersWithAccess: [],
  usersICareFor: [],

  isLoading: false,
  error: null,

  loadUsersWithAccess: async (patientId) => {
    set({ isLoading: true, error: null });
    try {
      const usersWithAccess = await caregiverApi.getUsersWithAccess(patientId);
      set({ usersWithAccess, isLoading: false });
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error ? error.message : 'Failed to load caregivers',
      });
    }
  },

  loadUsersICareFor: async (caregiverUserId) => {
    set({ isLoading: true, error: null });
    try {
      const usersICareFor =
        await caregiverApi.getUsersICareFor(caregiverUserId);
      set({ usersICareFor, isLoading: false });
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to load care recipients',
      });
    }
  },

  findUserByPhone: async (phone) => {
    return caregiverApi.findUserByPhone(phone);
  },

  inviteCaregiver: async (request) => {
    set({ isLoading: true, error: null });
    try {
      const caregiver = await caregiverApi.inviteCaregiver(request);
      set((state) => ({
        usersWithAccess: [...state.usersWithAccess, caregiver],
        isLoading: false,
      }));
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error ? error.message : 'Failed to invite caregiver',
      });
    }
  },

  updateCaregiverPermissions: async (request) => {
    set({ isLoading: true, error: null });
    try {
      const caregiver = await caregiverApi.updateCaregiverPermissions(request);
      set((state) => ({
        usersWithAccess: state.usersWithAccess.map((existing) =>
          existing.linkId === caregiver.linkId ? caregiver : existing
        ),
        isLoading: false,
      }));
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to update caregiver permissions',
      });
    }
  },

  respondToCaregiverRequest: async (request) => {
    set({ isLoading: true, error: null });
    try {
      const recipient = await caregiverApi.respondToCaregiverRequest(request);
      set((state) => ({
        usersICareFor: state.usersICareFor.map((existing) =>
          existing.linkId === recipient.linkId ? recipient : existing
        ),
        isLoading: false,
      }));
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to respond to caregiver request',
      });
    }
  },

  revokeCaregiverLink: async (linkId) => {
    const { usersWithAccess } = get();
    set({ isLoading: true, error: null });
    try {
      await caregiverApi.revokeCaregiverLink(linkId);
      set({
        usersWithAccess: usersWithAccess.map((existing) =>
          existing.linkId === linkId
            ? { ...existing, status: 'revoked' }
            : existing
        ),
        isLoading: false,
      });
    } catch (error) {
      set({
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to revoke caregiver access',
      });
    }
  },
}));
