import * as Dialog from '@radix-ui/react-dialog';
import { ModalContent } from '../../components/Modal.tsx';
import { Badge } from '../../components/Badge.tsx';
import { Button } from '../../components/Button.tsx';
import { formatDate } from '../../utils/formatDate.ts';
import type { DataCategory, MedicalRecord } from '../../api/types.ts';

interface RecordDetailModalProps {
  record: MedicalRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const categoryLabels: Record<DataCategory, string> = {
  diagnoses: 'Diagnosis',
  certificates: 'Certificate',
  analyses: 'Analysis',
  prescriptions: 'Prescription',
  patient_info: 'Patient info',
  other_med_info: 'Other medical info',
};

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
  const raw = record.raw;
  if (!raw) return [];
  const details: Detail[] = [];

  const quantity = raw.valueQuantity as
    { value?: number; unit?: string } | undefined;
  if (quantity?.value != null) {
    details.push({
      label: 'Value',
      value: `${quantity.value}${quantity.unit ? ` ${quantity.unit}` : ''}`,
    });
  }

  if (typeof raw.conclusion === 'string' && raw.conclusion !== record.title) {
    details.push({ label: 'Conclusion', value: raw.conclusion });
  }

  if (record.raw?.period?.start) {
    const { start, end } = record.raw.period;
    details.push({
      label: 'Period',
      value: end
        ? `${formatDate(start)} – ${formatDate(end)}`
        : `From ${formatDate(start)}`,
    });
  }

  if (typeof raw.class === 'string') {
    details.push({ label: 'Admission class', value: raw.class });
  }

  return details;
}

export function RecordDetailModal({
  record,
  open,
  onOpenChange,
}: RecordDetailModalProps) {
  if (!record) return null;

  const details = extraDetails(record);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <ModalContent
        title={record.title}
        description={[
          record.sourceLabel,
          record.date && formatDate(record.date),
        ]
          .filter(Boolean)
          .join(' · ')}
        className="max-w-lg"
      >
        <dl className="space-y-3">
          <div className="flex items-center justify-between gap-4">
            <dt className="text-sm text-ink-400">Type</dt>
            <dd>
              <Badge variant="neutral">{record.type}</Badge>
            </dd>
          </div>

          {record.category && (
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-ink-400">Category</dt>
              <dd>
                <Badge variant="neutral">
                  {categoryLabels[record.category]}
                </Badge>
              </dd>
            </div>
          )}

          {record.status && (
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-ink-400">Status</dt>
              <dd>
                <Badge
                  variant={record.status === 'stored' ? 'success' : 'danger'}
                >
                  {record.status === 'stored' ? 'Stored' : 'Rejected'}
                </Badge>
              </dd>
            </div>
          )}

          {record.fileName && (
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-ink-400">File</dt>
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
            <Button variant="ghost">Close</Button>
          </Dialog.Close>
        </div>
      </ModalContent>
    </Dialog.Root>
  );
}
