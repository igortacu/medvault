import { describe, expect, it } from 'vitest';
import type { Institution, InstitutionConnection } from '../../api/types';
import {
  connectable,
  latestConnections,
  resultMessage,
  scopeLabels,
  validateIdnp,
} from './connectionRules';

const institution = (id: string, type: Institution['type']): Institution => ({
  id,
  name: id,
  type,
  city: null,
});

const connection = (
  id: string,
  institutionId: string,
  status: InstitutionConnection['status'],
  consentedAt = '2026-10-18T12:00:00Z'
): InstitutionConnection => ({
  id,
  institution_id: institutionId,
  origin: 'auto_public',
  status,
  connected_at: null,
  consented_at: consentedAt,
});

describe('validateIdnp', () => {
  it('accepts 13 digits, ignoring spaces', () => {
    expect(validateIdnp('2001234567890')).toBeNull();
    expect(validateIdnp('2001 2345 67890')).toBeNull();
  });

  it('rejects empty, non-digit and wrong-length values', () => {
    expect(validateIdnp('')).toMatch(/enter/i);
    expect(validateIdnp('20012345678a0')).toMatch(/digits/i);
    expect(validateIdnp('123')).toMatch(/13/);
  });
});

describe('latestConnections', () => {
  it('keeps the newest attempt per institution and drops revoked ones', () => {
    const latest = latestConnections([
      connection('c3', 'a', 'active'),
      connection('c2', 'a', 'error'),
      connection('c1', 'b', 'revoked'),
    ]);
    expect(latest.get('a')?.id).toBe('c3');
    expect(latest.has('b')).toBe(false);
  });
});

describe('connectable', () => {
  it('lists institutions of a type without a live connection', () => {
    const institutions = [
      institution('pub-1', 'public'),
      institution('pub-2', 'public'),
      institution('priv', 'private'),
    ];
    const latest = latestConnections([
      connection('c1', 'pub-1', 'active'),
      connection('c2', 'pub-2', 'no_match'),
    ]);
    expect(
      connectable(institutions, latest, 'public').map((i) => i.id)
    ).toEqual(['pub-2']);
    expect(
      connectable(institutions, latest, 'private').map((i) => i.id)
    ).toEqual(['priv']);
  });
});

describe('scopeLabels', () => {
  it('maps read scopes to labels and skips the rest', () => {
    expect(
      scopeLabels([
        'patient/Condition.read',
        'patient/Observation.read',
        'offline_access',
        'patient/Unknown.read',
      ])
    ).toEqual(['Diagnoses', 'Measurements and lab results', 'Unknown']);
    expect(scopeLabels(null)).toEqual([]);
  });
});

describe('resultMessage', () => {
  it('summarises a batch from the public connections', () => {
    const institutions = [
      institution('pub-1', 'public'),
      institution('pub-2', 'public'),
      institution('priv', 'private'),
    ];
    const latest = latestConnections([
      connection('c1', 'pub-1', 'active'),
      connection('c2', 'pub-2', 'no_match'),
      connection('c3', 'priv', 'active'),
    ]);
    expect(resultMessage('done', institutions, latest)).toMatchObject({
      title: 'Connected to 1 public institution',
      description: '1 could not be connected. See the list below.',
    });
  });

  it('does not count unticked institutions as failures', () => {
    const institutions = [
      institution('pub-1', 'public'),
      institution('pub-2', 'public'),
    ];
    const latest = latestConnections([connection('c1', 'pub-1', 'active')]);
    expect(resultMessage('done', institutions, latest)?.description).toBe(
      undefined
    );
  });

  it('only counts the latest batch, not older connections', () => {
    const institutions = [
      institution('old', 'public'),
      institution('new-1', 'public'),
      institution('new-2', 'public'),
    ];
    const latest = latestConnections([
      connection('c3', 'new-2', 'active', '2026-10-18T12:00:01Z'),
      connection('c2', 'new-1', 'active', '2026-10-18T12:00:00Z'),
      connection('c1', 'old', 'active', '2026-01-10T09:05:00Z'),
    ]);
    expect(resultMessage('done', institutions, latest)?.title).toBe(
      'Connected to 2 public institutions'
    );
  });

  it('ignores unknown results', () => {
    expect(resultMessage('whatever', [], new Map())).toBeNull();
  });
});
