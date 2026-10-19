import enAuth from './locales/en/auth.json';
import enCaregiver from './locales/en/caregiver.json';
import enCommon from './locales/en/common.json';
import enDocuments from './locales/en/documents.json';
import enInstitutions from './locales/en/institutions.json';
import enNav from './locales/en/nav.json';
import enProfile from './locales/en/profile.json';
import roAuth from './locales/ro/auth.json';
import roCaregiver from './locales/ro/caregiver.json';
import roCommon from './locales/ro/common.json';
import roDocuments from './locales/ro/documents.json';
import roInstitutions from './locales/ro/institutions.json';
import roNav from './locales/ro/nav.json';
import roProfile from './locales/ro/profile.json';
import ruAuth from './locales/ru/auth.json';
import ruCaregiver from './locales/ru/caregiver.json';
import ruCommon from './locales/ru/common.json';
import ruDocuments from './locales/ru/documents.json';
import ruInstitutions from './locales/ru/institutions.json';
import ruNav from './locales/ru/nav.json';
import ruProfile from './locales/ru/profile.json';

export const NAMESPACES = [
  'common',
  'auth',
  'nav',
  'documents',
  'caregiver',
  'profile',
  'institutions',
] as const;

// English is the reference for the key types (see i18next.d.ts); the other
// languages carry their own plural forms, so a test checks their keys instead.
export const en = {
  common: enCommon,
  auth: enAuth,
  nav: enNav,
  documents: enDocuments,
  caregiver: enCaregiver,
  profile: enProfile,
  institutions: enInstitutions,
};

export const resources = {
  en,
  ro: {
    common: roCommon,
    auth: roAuth,
    nav: roNav,
    documents: roDocuments,
    caregiver: roCaregiver,
    profile: roProfile,
    institutions: roInstitutions,
  },
  ru: {
    common: ruCommon,
    auth: ruAuth,
    nav: ruNav,
    documents: ruDocuments,
    caregiver: ruCaregiver,
    profile: ruProfile,
    institutions: ruInstitutions,
  },
};
