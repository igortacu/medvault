import { describe, expect, it } from 'vitest';
import { LANGUAGES } from './languages';
import { NAMESPACES, resources } from './resources';
import apiReadme from '../../../docs/api/README.md?raw';

type Tree = { [key: string]: string | Tree };

const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;

function flatten(tree: Tree, prefix = ''): Record<string, string> {
  return Object.entries(tree).reduce<Record<string, string>>(
    (flat, [key, value]) =>
      typeof value === 'string'
        ? { ...flat, [prefix + key]: value }
        : { ...flat, ...flatten(value, `${prefix}${key}.`) },
    {}
  );
}

const strings = (language: keyof typeof resources, ns: string) =>
  flatten((resources[language] as unknown as Record<string, Tree>)[ns]);

const baseKeys = (flat: Record<string, string>) =>
  [
    ...new Set(Object.keys(flat).map((k) => k.replace(PLURAL_SUFFIX, ''))),
  ].sort();

const placeholders = (text: string) =>
  [...text.matchAll(/{{\s*(\w+)[^}]*}}|<(\w+)>/g)]
    .map((m) => m[1] ?? `<${m[2]}>`)
    .filter((name) => name !== 'count')
    .sort();

describe.each(NAMESPACES)('the %s namespace', (ns) => {
  const en = strings('en', ns);

  it.each(['ro', 'ru'] as const)(
    'has the same keys in %s as in English',
    (lng) => {
      expect(baseKeys(strings(lng, ns))).toEqual(baseKeys(en));
    }
  );

  it.each(LANGUAGES.map((l) => l.code))(
    'has every plural form %s needs',
    (lng) => {
      const flat = strings(lng, ns);
      const forms = new Intl.PluralRules(lng).resolvedOptions()
        .pluralCategories;
      const plurals = new Set(
        Object.keys(flat)
          .filter((k) => PLURAL_SUFFIX.test(k))
          .map((k) => k.replace(PLURAL_SUFFIX, ''))
      );
      for (const key of plurals) {
        for (const form of forms)
          expect(flat).toHaveProperty([`${key}_${form}`]);
      }
    }
  );

  it.each(['ro', 'ru'] as const)(
    'keeps the interpolations and tags of English in %s',
    (lng) => {
      const flat = strings(lng, ns);
      for (const [key, text] of Object.entries(en)) {
        if (PLURAL_SUFFIX.test(key)) continue;
        expect([key, placeholders(flat[key])]).toEqual([
          key,
          placeholders(text),
        ]);
      }
    }
  );
});

describe('Romanian text', () => {
  it('uses comma-below ș and ț, not the cedilla forms', () => {
    for (const ns of NAMESPACES) {
      for (const text of Object.values(strings('ro', ns))) {
        expect(text).not.toMatch(/[şţŞŢ]/);
      }
    }
  });
});

describe('document subtype labels', () => {
  it('cover every type code the API documents', () => {
    const section = apiReadme
      .split('## type values per category')[1]
      .split('---')[0]
      // Only the "**category** — codes" paragraphs, not the intro sentence.
      .split(/\r?\n\r?\n/)
      .filter((paragraph) => paragraph.startsWith('**'))
      .join('\n');
    const codes = [...section.matchAll(/`([a-z_]+)`/g)].map((m) => m[1]);
    expect(codes.length).toBeGreaterThan(30);
    for (const lng of LANGUAGES.map((l) => l.code)) {
      const labels = resources[lng].documents.docType as Record<string, string>;
      for (const code of codes)
        expect([lng, code, labels[code]]).not.toContain(undefined);
    }
  });
});
