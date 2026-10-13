/** Mirrors the backend password rules (auth/validation.py). The backend is authoritative. */
export function passwordChecks(password: string) {
  return [
    { label: '10–128 characters', ok: password.length >= 10 && password.length <= 128 },
    { label: 'A lowercase letter', ok: /[a-z]/.test(password) },
    { label: 'An uppercase letter', ok: /[A-Z]/.test(password) },
    { label: 'A digit', ok: /[0-9]/.test(password) },
    { label: 'A special character', ok: /[^A-Za-z0-9]/.test(password) },
  ];
}
