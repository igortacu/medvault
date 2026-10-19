import { beforeEach, describe, expect, it } from 'vitest';
import type { MedicalRecord } from '../../api/types';
import i18n from '../../i18n';
import { recordTypeLabel } from './recordLabels';

const record = (overrides: Partial<MedicalRecord>): MedicalRecord => ({
  id: 'r1',
  source: 'institution',
  sourceLabel: 'IMSP Institutul de Cardiologie',
  institutionId: null,
  category: 'certificates',
  documentTypeCode: null,
  resourceType: 'DocumentReference',
  title: 'Certificat',
  date: null,
  ...overrides,
});

describe('recordTypeLabel', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it("names an institution's document by its subtype, not as an upload", () => {
    const label = recordTypeLabel(
      record({ documentTypeCode: 'vaccination_certificate' })
    );
    expect(label).toBe(i18n.t('documents:docType.vaccination_certificate'));
    expect(label).not.toBe(i18n.t('documents:resourceType.DocumentReference'));
  });

  it('falls back to the resource type for unknown or missing subtypes', () => {
    expect(
      recordTypeLabel(
        record({ resourceType: 'Observation', documentTypeCode: 'nope' })
      )
    ).toBe(i18n.t('documents:resourceType.Observation'));
    expect(recordTypeLabel(record({ resourceType: 'Mystery' }))).toBe(
      'Mystery'
    );
  });
});
