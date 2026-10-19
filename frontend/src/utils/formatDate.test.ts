import { afterAll, describe, expect, it } from 'vitest';
import i18n from '../i18n';
import { formatDate } from './formatDate';

afterAll(async () => {
  await i18n.changeLanguage('ro');
});

describe('formatDate', () => {
  it.each([
    ['ro', '19 oct. 2026'],
    ['en', '19 Oct 2026'],
    ['ru', '19 окт. 2026 г.'],
  ])('formats in the %s locale', async (language, expected) => {
    await i18n.changeLanguage(language);
    expect(formatDate('2026-10-19')).toBe(expected);
  });
});
