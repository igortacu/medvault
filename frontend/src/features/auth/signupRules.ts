/**
 * Mirrors the backend sign-up field rules (auth/validation.py) so mistakes show up
 * as the user types. The backend is authoritative and still validates everything.
 * Each validator returns an error message in the active language, or null when
 * the value is fine.
 */

import i18n from '../../i18n';

const NAME_RE = /^\p{L}+(?:[ '’-]\p{L}+)*$/u;
const PHONE_RE = /^\+373[0-9]{8}$/;

export function validateName(value: string): string | null {
  const name = value.normalize('NFC').trim();
  if (!name) return i18n.t('auth:validation.required');
  if (name.length < 2 || name.length > 50) {
    return i18n.t('auth:validation.nameLength');
  }
  if (!NAME_RE.test(name)) {
    return i18n.t('auth:validation.nameChars');
  }
  return null;
}

/** Accept +373XXXXXXXX, 373XXXXXXXX, 00373XXXXXXXX or 0XXXXXXXX; return +373XXXXXXXX or null. */
export function normalizePhone(value: string): string | null {
  let raw = value.replace(/[\s\-().]/g, '');
  if (raw.startsWith('00373')) raw = '+' + raw.slice(2);
  else if (raw.startsWith('373')) raw = '+' + raw;
  else if (/^0[0-9]{8}$/.test(raw)) raw = '+373' + raw.slice(1);
  return PHONE_RE.test(raw) ? raw : null;
}

export function validatePhone(value: string): string | null {
  return normalizePhone(value) ? null : i18n.t('auth:validation.phone');
}

/** Local calendar date as YYYY-MM-DD, the format of <input type="date">. */
export function isoDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function validateDob(value: string, today = new Date()): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value))
    return i18n.t('auth:validation.dobRequired');
  if (value > isoDate(today)) return i18n.t('auth:validation.dobFuture');
  const oldest = new Date(today);
  oldest.setFullYear(today.getFullYear() - 120);
  if (value < isoDate(oldest)) return i18n.t('auth:validation.dobInvalid');
  return null;
}

export function validateConfirm(
  password: string,
  confirm: string
): string | null {
  if (!confirm) return i18n.t('auth:validation.confirmRequired');
  return password === confirm
    ? null
    : i18n.t('auth:validation.confirmMismatch');
}
