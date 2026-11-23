/**
 * Mirrors the backend measurement rules (documents/patient_info.py and the
 * patient_profiles CHECKs) so mistakes show up before saving. The backend is
 * authoritative and still validates everything.
 */

import i18n from '../../i18n';

export const WEIGHT_MAX_KG = 500;
export const HEIGHT_MAX_CM = 300;

// Up to 3 integer digits and the column's decimals: numeric(5,2) / numeric(5,1).
const WEIGHT_RE = /^\d{1,3}(?:\.\d{1,2})?$/;
const HEIGHT_RE = /^\d{1,3}(?:\.\d)?$/;

export type ParsedMeasurement =
  { ok: true; value: number | undefined } | { ok: false; error: string };

function parse(
  raw: string,
  pattern: RegExp,
  max: number,
  error: () => string
): ParsedMeasurement {
  // Romanian and Russian write decimals with a comma.
  const text = raw.trim().replace(',', '.');
  if (!text) return { ok: true, value: undefined };
  const value = Number(text);
  if (!pattern.test(text) || !(value > 0 && value < max)) {
    return { ok: false, error: error() };
  }
  return { ok: true, value };
}

/** Empty input means "leave unchanged" and parses to undefined. */
export function parseWeight(raw: string): ParsedMeasurement {
  return parse(raw, WEIGHT_RE, WEIGHT_MAX_KG, () =>
    i18n.t('profile:edit.weightInvalid', { max: WEIGHT_MAX_KG })
  );
}

/** Empty input means "leave unchanged" and parses to undefined. */
export function parseHeight(raw: string): ParsedMeasurement {
  return parse(raw, HEIGHT_RE, HEIGHT_MAX_CM, () =>
    i18n.t('profile:edit.heightInvalid', { max: HEIGHT_MAX_CM })
  );
}
