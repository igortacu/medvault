// Authentication API (Epic 1). Every flow is two-step: credentials -> SMS code.
// In `mock` mode a fixed code ("123456") is accepted so the UI works without a backend.

import type { User } from './types';
import { ApiError, RateLimited, rateLimitedFrom } from './errors';
import mockDataService from './mockDatasetService';

const BASE_URL: string =
  (import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_API_BASE_URL || '/api';

const IS_MOCK = import.meta.env.MODE === 'mock';
export const MOCK_CODE = '123456';
// In mock mode this phone and this code answer 429, to try the cooldown UI.
export const MOCK_RATE_LIMITED_PHONE = '+37369999999';
export const MOCK_RATE_LIMITED_CODE = '999999';
const MOCK_RETRY_AFTER = 15 * 60;

export interface Challenge {
  challengeId: string;
  /** Seconds until the code expires. */
  expiresIn: number;
}

export interface SignupInput {
  firstName: string;
  lastName: string;
  phone: string;
  dateOfBirth: string; // YYYY-MM-DD
  password: string;
}

/** Field-level validation failures from the backend (HTTP 422). */
export class FieldErrors extends ApiError {
  readonly errors: Record<string, string>;

  constructor(errors: Record<string, string>) {
    super('Validation failed', 422);
    this.errors = errors;
  }
}

export { RateLimited };

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 429) throw rateLimitedFrom(res);
    if (res.status === 422) {
      const payload = await res.json().catch(() => null);
      const errors = payload?.detail?.errors;
      if (errors && typeof errors === 'object') throw new FieldErrors(errors);
    }
    // Deliberately generic: raw backend detail is never shown to the user.
    throw new ApiError(`Request failed: POST ${path} (${res.status})`, res.status);
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

interface WireChallenge {
  challenge_id: string;
  expires_in: number;
}

const toChallenge = (w: WireChallenge): Challenge => ({
  challengeId: w.challenge_id,
  expiresIn: w.expires_in,
});

const mockChallenge: Challenge = { challengeId: 'mock', expiresIn: 300 };

function mockRateLimit(value: string) {
  if (value === MOCK_RATE_LIMITED_PHONE || value === MOCK_RATE_LIMITED_CODE) {
    throw new RateLimited(MOCK_RETRY_AFTER);
  }
}

async function mockVerify(code: string): Promise<User> {
  mockRateLimit(code);
  if (code !== MOCK_CODE) throw new ApiError('Invalid code', 400);
  return mockDataService.getCurrentUser();
}

export interface AuthApi {
  login(phone: string, password: string): Promise<Challenge>;
  verifyLogin(challengeId: string, code: string): Promise<User>;
  signup(input: SignupInput): Promise<Challenge>;
  verifySignup(challengeId: string, code: string): Promise<User>;
  resendCode(challengeId: string): Promise<Challenge>;
  requestPasswordReset(phone: string): Promise<Challenge>;
  verifyPasswordReset(challengeId: string, code: string): Promise<string>;
  confirmPasswordReset(resetToken: string, newPassword: string): Promise<void>;
}

const realAuthApi: AuthApi = {
  async login(phone, password) {
    return toChallenge(await post('/auth/login', { phone, password }));
  },
  verifyLogin: (challengeId, code) =>
    post<User>('/auth/login/verify', { challenge_id: challengeId, code }),

  async signup(input) {
    return toChallenge(
      await post('/auth/signup', {
        first_name: input.firstName,
        last_name: input.lastName,
        phone: input.phone,
        date_of_birth: input.dateOfBirth,
        password: input.password,
      })
    );
  },
  verifySignup: (challengeId, code) =>
    post<User>('/auth/signup/verify', { challenge_id: challengeId, code }),

  async resendCode(challengeId) {
    return toChallenge(await post('/auth/sms/resend', { challenge_id: challengeId }));
  },

  async requestPasswordReset(phone) {
    return toChallenge(await post('/auth/password-reset/request', { phone }));
  },
  async verifyPasswordReset(challengeId, code) {
    const res = await post<{ reset_token: string }>('/auth/password-reset/verify', {
      challenge_id: challengeId,
      code,
    });
    return res.reset_token;
  },
  async confirmPasswordReset(resetToken, newPassword) {
    await post('/auth/password-reset/confirm', {
      reset_token: resetToken,
      new_password: newPassword,
    });
  },
};

const mockAuthApi: AuthApi = {
  async login(phone) {
    mockRateLimit(phone);
    return mockChallenge;
  },
  verifyLogin: (_id, code) => mockVerify(code),
  signup: async () => mockChallenge,
  verifySignup: (_id, code) => mockVerify(code),
  resendCode: async () => mockChallenge,
  async requestPasswordReset(phone) {
    mockRateLimit(phone);
    return mockChallenge;
  },
  async verifyPasswordReset(_id, code) {
    mockRateLimit(code);
    if (code !== MOCK_CODE) throw new ApiError('Invalid code', 400);
    return 'mock-reset-token';
  },
  confirmPasswordReset: async () => undefined,
};

export const authApi: AuthApi = IS_MOCK ? mockAuthApi : realAuthApi;
