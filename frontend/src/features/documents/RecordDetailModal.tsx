import * as Dialog from '@radix-ui/react-dialog';
import { useTranslation } from 'react-i18next';
import { ModalContent } from '../../components/Modal.tsx';
import { Badge } from '../../components/Badge.tsx';
import { Button } from '../../components/Button.tsx';
import { formatDate } from '../../utils/formatDate.ts';
import type { MedicalRecord } from '../../api/types.ts';
import i18n from '../../i18n';
import { localeFor } from '../../i18n/languages';
import useOriginalDocument, { canOpenOriginal } from './useOriginalDocument.ts';
import { recordSource, recordTitle, recordTypeLabel } from './recordLabels.ts';
import { useDatasetStore } from '../../store/datasetStore.ts';
import { RecordExportButton } from '../exports/RecordExportButton.tsx';
interface RecordDetailModalProps {
  record: MedicalRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface Detail {
  label: string;
  value: string;
}

/**
 * Pulls the fields that don't fit on the compact card (lab values, report
 * conclusions, stay periods, ...) out of the raw FHIR resource. Skips a
 * conclusion that's already showing as the modal title, so it's not
 * repeated on the diagnostic-report records that fall back to it.
 */
function extraDetails(record: MedicalRecord): Detail[] {
  const t = i18n.getFixedT(null, 'documents');
  const raw = record.raw;
  if (!raw) return [];
  const details: Detail[] = [];

  const quantity = raw.valueQuantity as
    { value?: number; unit?: string } | undefined;
  if (quantity?.value != null) {
    const value = quantity.value.toLocaleString(localeFor(i18n.language));
    details.push({
      label: t('detail.value'),
      value: quantity.unit ? `${value} ${quantity.unit}` : value,
    });
  }

  if (typeof raw.conclusion === 'string' && raw.conclusion !== record.title) {
    details.push({ label: t('detail.conclusion'), value: raw.conclusion });
  }

  if (record.raw?.period?.start) {
    const { start, end } = record.raw.period;
    details.push({
      label: t('detail.period'),
      value: end
        ? `${formatDate(start)} – ${formatDate(end)}`
        : t('detail.from', { date: formatDate(start) }),
    });
  }

  if (typeof raw.class === 'string') {
    details.push({ label: t('detail.admissionClass'), value: raw.class });
  }

  return details;
}

export function RecordDetailModal({
  record,
  open,
  onOpenChange,
}: RecordDetailModalProps) {
  const { t } = useTranslation(['documents', 'common']);
  const original = useOriginalDocument(record, open);
  // Export is the patient's own action: hidden while viewing someone's vault.
  const ownPatientId = useDatasetStore((state) =>
    state.activeRecipient ? null : (state.currentUser?.id ?? null)
  );

  if (!record) return null;

  const details = extraDetails(record);
  const mimeType =
    original.status === 'ready' ? original.mimeType : record.mimeType;
  const isImage = mimeType?.startsWith('image/') ?? false;
  // Originals arrive as in-memory blob URLs, so a PDF can be shown inline.
  const inlinePdf =
    original.status === 'ready' && mimeType === 'application/pdf';

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <ModalContent
        title={recordTitle(record)}
        description={[
          recordSource(record),
          record.date && formatDate(record.date),
        ]
          .filter(Boolean)
          .join(' · ')}
        className="max-w-lg"
      >
        {canOpenOriginal(record) && (
          <div className="mb-4 space-y-2">
            {original.status === 'loading' && (
              <div className="flex h-40 items-center justify-center rounded-card bg-primary-50 text-sm text-ink-400">
                {t('detail.loadingOriginal')}
              </div>
            )}

            {original.status === 'error' && (
              <div className="rounded-card bg-coral-400/15 px-3 py-2 text-sm text-coral-500">
                {original.message}
              </div>
            )}

            {original.status === 'ready' && isImage && (
              <img
                src={original.url}
                alt={recordTitle(record)}
                className="max-h-80 w-full rounded-card object-contain"
              />
            )}

            {inlinePdf && (
              <iframe
                src={original.url}
                title={recordTitle(record)}
                className="h-80 w-full rounded-card border border-ink-400/20"
              />
            )}

            {original.status === 'ready' && record.source === 'institution' && (
              <p className="text-xs text-ink-400">
                {t('detail.originalFromInstitution', {
                  institution: record.sourceLabel,
                })}
              </p>
            )}

            {original.status === 'ready' && !isImage && (
              <a
                href={original.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex text-sm font-medium text-primary-600 underline underline-offset-2 hover:text-primary-700"
              >
                {t('detail.viewOriginal')}
              </a>
            )}
          </div>
        )}

        {ownPatientId && (
          <div className="mb-4">
            <RecordExportButton record={record} patientId={ownPatientId} />
          </div>
        )}

        <dl className="space-y-3">
          <div className="flex items-center justify-between gap-4">
            <dt className="text-sm text-ink-400">{t('detail.type')}</dt>
            <dd>
              <Badge variant="neutral">{recordTypeLabel(record)}</Badge>
            </dd>
          </div>

          {record.category && (
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-ink-400">{t('detail.category')}</dt>
              <dd>
                <Badge variant="neutral">
                  {t(`common:categoryOne.${record.category}`)}
                </Badge>
              </dd>
            </div>
          )}

          {record.status && (
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-ink-400">{t('detail.status')}</dt>
              <dd>
                <Badge
                  variant={record.status === 'stored' ? 'success' : 'danger'}
                >
                  {t(`status.${record.status}`)}
                </Badge>
              </dd>
            </div>
          )}

          {record.fileName && (
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-ink-400">{t('detail.file')}</dt>
              <dd className="text-sm text-ink-900">{record.fileName}</dd>
            </div>
          )}

          {details.map((detail) => (
            <div
              key={detail.label}
              className="flex items-start justify-between gap-4"
            >
              <dt className="shrink-0 text-sm text-ink-400">{detail.label}</dt>
              <dd className="text-right text-sm text-ink-900">
                {detail.value}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 flex justify-end">
          <Dialog.Close asChild>
            <Button variant="ghost">{t('common:close')}</Button>
          </Dialog.Close>
        </div>
      </ModalContent>
    </Dialog.Root>
  );
}
