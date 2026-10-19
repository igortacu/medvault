// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import i18n, { LANGUAGE_STORAGE_KEY, savedLanguage, setLanguage } from '.';

afterEach(async () => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  await i18n.changeLanguage('ro');
});

describe('savedLanguage', () => {
  it('defaults to Romanian', () => {
    expect(savedLanguage()).toBe('ro');
  });

  it('returns a saved supported language', () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'ru');
    expect(savedLanguage()).toBe('ru');
  });

  it('ignores an unsupported saved value', () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'de');
    expect(savedLanguage()).toBe('ro');
  });

  it('falls back to Romanian when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    expect(savedLanguage()).toBe('ro');
  });
});

describe('setLanguage', () => {
  it('switches the language, saves it and sets <html lang>', async () => {
    await setLanguage('en');
    expect(i18n.language).toBe('en');
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');
    expect(document.documentElement.lang).toBe('en');
    expect(i18n.t('auth:signIn')).toBe('Sign in');
  });

  it('still switches when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'QuotaExceededError');
    });
    await setLanguage('ru');
    expect(i18n.t('auth:signIn')).toBe('Войти');
  });
});

describe('plural forms', () => {
  it('follows Romanian and Russian rules', async () => {
    const age = (count: number) => i18n.t('caregiver:card.age', { count });
    await i18n.changeLanguage('ro');
    expect([1, 5, 20].map(age)).toEqual(['1 an', '5 ani', '20 de ani']);
    await i18n.changeLanguage('ru');
    expect([1, 3, 5, 21].map(age)).toEqual([
      '1 год',
      '3 года',
      '5 лет',
      '21 год',
    ]);
    await i18n.changeLanguage('en');
    expect([1, 2].map(age)).toEqual(['1 year', '2 years']);
  });
});
