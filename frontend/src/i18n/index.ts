import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import {
  DEFAULT_LANGUAGE,
  isLanguage,
  LANGUAGES,
  type Language,
} from './languages';
import { NAMESPACES, resources } from './resources';

export const LANGUAGE_STORAGE_KEY = 'medvault.language';

/** The language the user picked before, or Romanian. Storage may be blocked. */
export function savedLanguage(): Language {
  try {
    const saved = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isLanguage(saved)) return saved;
  } catch {
    // Private mode or blocked site data: fall back to the default.
  }
  return DEFAULT_LANGUAGE;
}

/** Switches the UI language and remembers the choice for the next visit. */
export function setLanguage(language: Language) {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Not remembered, but the switch itself still applies.
  }
  return i18n.changeLanguage(language);
}

// Screen readers and hyphenation follow <html lang>. (No document in unit tests.)
i18n.on('languageChanged', (language) => {
  if (typeof document !== 'undefined') document.documentElement.lang = language;
});

void i18n.use(initReactI18next).init({
  resources,
  lng: savedLanguage(),
  // Only reached if a key is missing in ro/ru; the parity test guards that.
  fallbackLng: 'en',
  supportedLngs: LANGUAGES.map((l) => l.code),
  ns: NAMESPACES,
  defaultNS: 'common',
  // Everything is bundled, so initialise synchronously before the first render.
  initAsync: false,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

export default i18n;
