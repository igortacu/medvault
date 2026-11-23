import { describe, expect, it } from 'vitest';
import { parseHeight, parseWeight } from './measurementRules.ts';

describe('parseWeight', () => {
  it('accepts decimals with a dot or a comma', () => {
    expect(parseWeight('72.4')).toEqual({ ok: true, value: 72.4 });
    expect(parseWeight(' 72,45 ')).toEqual({ ok: true, value: 72.45 });
    expect(parseWeight('3')).toEqual({ ok: true, value: 3 });
  });

  it('treats an empty field as unchanged', () => {
    expect(parseWeight('   ')).toEqual({ ok: true, value: undefined });
  });

  it('rejects out-of-range, too precise and non-numeric values', () => {
    for (const raw of ['0', '500', '-5', '72.456', 'abc', '1e2', '72.']) {
      expect(parseWeight(raw).ok).toBe(false);
    }
  });
});

describe('parseHeight', () => {
  it('accepts one decimal', () => {
    expect(parseHeight('176.5')).toEqual({ ok: true, value: 176.5 });
    expect(parseHeight('164,0')).toEqual({ ok: true, value: 164 });
  });

  it('rejects out-of-range and too precise values', () => {
    for (const raw of ['0', '300', '176.55', '1000']) {
      expect(parseHeight(raw).ok).toBe(false);
    }
  });
});
