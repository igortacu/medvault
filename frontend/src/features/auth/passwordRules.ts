/** Mirrors the backend password rules (auth/validation.py). The backend is authoritative. */
export function passwordChecks(password: string) {
  return [
    { rule: 'length', ok: password.length >= 10 && password.length <= 128 },
    { rule: 'lowercase', ok: /[a-z]/.test(password) },
    { rule: 'uppercase', ok: /[A-Z]/.test(password) },
    { rule: 'digit', ok: /[0-9]/.test(password) },
    { rule: 'special', ok: /[^A-Za-z0-9]/.test(password) },
  ] as const;
}
