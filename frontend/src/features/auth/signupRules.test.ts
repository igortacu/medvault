import { describe, expect, it } from 'vitest';
import {
  normalizeEmail,
  normalizePhone,
  validateConfirm,
  validateDob,
  validateName,
} from './signupRules.ts';

describe('validateName', () => {
  it('accepts letters, Romanian diacritics, hyphens and apostrophes', () => {
    for (const name of [
      'Ana',
      'Ștefan',
      'Anne-Marie',
      "O'Brien",
      'Van Damme',
    ]) {
      expect(validateName(name)).toBeNull();
    }
  });

  it('rejects digits, stray punctuation and bad lengths', () => {
    for (const name of ['A', 'Ana1', '-Ana', 'Ana--Maria', 'x'.repeat(51)]) {
      expect(validateName(name)).not.toBeNull();
    }
  });
});

describe('normalizePhone', () => {
  it('normalises the formats the backend accepts', () => {
    expect(normalizePhone('+373 69 000 000')).toBe('+37369000000');
    expect(normalizePhone('37369000000')).toBe('+37369000000');
    expect(normalizePhone('0037369000000')).toBe('+37369000000');
    expect(normalizePhone('069000000')).toBe('+37369000000');
  });

  it('rejects anything else', () => {
    expect(normalizePhone('+373')).toBeNull();
    expect(normalizePhone('+40712345678')).toBeNull();
    expect(normalizePhone('+3736900000')).toBeNull();
  });
});

describe('validateDob', () => {
  const today = new Date(2026, 9, 16);

  it('accepts past dates within 120 years', () => {
    expect(validateDob('1990-05-01', today)).toBeNull();
    expect(validateDob('2026-10-16', today)).toBeNull();
  });

  it('rejects empty, future and implausibly old dates', () => {
    expect(validateDob('', today)).not.toBeNull();
    expect(validateDob('2026-10-17', today)).not.toBeNull();
    expect(validateDob('1906-10-15', today)).not.toBeNull();
  });
});

describe('validateConfirm', () => {
  it('requires a matching repeat', () => {
    expect(validateConfirm('Secret-Pass1', '')).not.toBeNull();
    expect(validateConfirm('Secret-Pass1', 'Secret-Pass2')).not.toBeNull();
    expect(validateConfirm('Secret-Pass1', 'Secret-Pass1')).toBeNull();
  });
});

describe('normalizeEmail', () => {
  it('trims and lowercases the addresses the backend accepts', () => {
    expect(normalizeEmail('  Maria.Rusu@Example.COM ')).toBe(
      'maria.rusu@example.com'
    );
    expect(normalizeEmail('a+tag@mail.co.md')).toBe('a+tag@mail.co.md');
  });

  it('rejects what the backend would refuse', () => {
    for (const bad of [
      '',
      'maria',
      'maria@',
      '@example.com',
      'maria@example',
      'ma ria@example.com',
      'maria@exa..mple.com',
      'mariă@example.com',
      'a'.repeat(250) + '@example.com',
    ]) {
      expect(normalizeEmail(bad)).toBeNull();
    }
  });
});
