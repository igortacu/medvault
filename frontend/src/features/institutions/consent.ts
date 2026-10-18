// The consent the patient agrees to before any request goes to an
// institution. The backend records the version with each connection, so
// bump it whenever this wording changes.
export const CONSENT_TEXT_VERSION = '2026-10';

export const CONSENT_POINTS = [
  'MedVault sends your IDNP once to each institution listed, only so it can find your records. MedVault never stores your IDNP.',
  'Each institution shares read-only access to your diagnoses, lab results, prescriptions, certificates and visits.',
  'Records are fetched live when you open them and are not copied into MedVault.',
  'You can disconnect an institution at any time; its records then disappear from MedVault straight away.',
];
