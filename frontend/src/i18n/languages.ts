export const LANGUAGES = [
  { code: 'ro', short: 'RO', name: 'Română', locale: 'ro-RO' },
  { code: 'en', short: 'EN', name: 'English', locale: 'en-GB' },
  { code: 'ru', short: 'RU', name: 'Русский', locale: 'ru-RU' },
] as const;

export type Language = (typeof LANGUAGES)[number]['code'];

export const DEFAULT_LANGUAGE: Language = 'ro';

export function isLanguage(value: unknown): value is Language {
  return LANGUAGES.some((l) => l.code === value);
}

/** The Intl locale for dates and numbers in a language. */
export function localeFor(language: string | undefined): string {
  return (
    LANGUAGES.find((l) => l.code === language)?.locale ??
    LANGUAGES.find((l) => l.code === DEFAULT_LANGUAGE)!.locale
  );
}
