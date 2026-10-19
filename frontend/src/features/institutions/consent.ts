// The consent the patient agrees to before any request goes to an
// institution. The backend records the version with each connection, so
// bump it whenever what these points say changes. The Romanian, English and
// Russian wordings (institutions:consent.* in src/i18n/locales) are
// translations of one text and share its version; change them together.
export const CONSENT_TEXT_VERSION = '2026-10';

/** Keys of the consent points, in the order they are shown. */
export const CONSENT_POINTS = [
  'idnp',
  'readOnly',
  'live',
  'disconnect',
] as const;
