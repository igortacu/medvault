import { X } from 'lucide-react';
import { Button } from '../../components/Button.tsx';
import { Input } from '../../components/Input.tsx';
import type {
  Institution,
  MedicalRecord,
  MedicalRecordFilters,
} from '../../api/types.ts';
interface DocumentsFilterModalProps {
  records: MedicalRecord[];
  institutions: Institution[];
  value: MedicalRecordFilters;
  isLoading?: boolean;
  onChange: <K extends keyof MedicalRecordFilters>(
    key: K,
    value: MedicalRecordFilters[K]
  ) => void;
  onApply: () => void;
  onClose: () => void;
}
export function DocumentsFilterModal({
  records,
  institutions,
  value,
  isLoading = false,
  onChange,
  onApply,
  onClose,
}: DocumentsFilterModalProps) {
  const documentTypes = Array.from(
    new Map(
      records
        .filter((record) => record.documentTypeCode != null)
        .map((record) => [
          record.documentTypeCode as string,
          record.type ?? record.documentTypeCode,
        ])
    ).entries()
  );
  return (
    <div
      className="absolute left-0 top-full z-50 mt-2 w-[380px] rounded-card border border-ink-400/20 bg-white p-5 shadow-lg"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="w-full max-w-md rounded-card border border-ink-400/20 bg-white p-5 shadow-lg">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink-900">
            Filter documents
          </h2>
          <button
            type="button"
            aria-label="Close filters"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-500 transition hover:bg-ink-100 hover:text-ink-900"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-800">
              Document type
            </label>
            <select
              aria-label="Document type"
              value={value.documentTypeCode ?? ''}
              onChange={(event) =>
                onChange('documentTypeCode', event.target.value)
              }
              className="h-11 w-full rounded-xl border border-ink-400/30 bg-white px-4 text-sm text-ink-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All document types</option>
              {documentTypes.map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-800">
              Source
            </label>
            <select
              aria-label="Document source"
              value={value.source ?? ''}
              onChange={(event) =>
                onChange(
                  'source',
                  event.target.value as MedicalRecordFilters['source']
                )
              }
              className="h-11 w-full rounded-xl border border-ink-400/30 bg-white px-4 text-sm text-ink-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All sources</option>
              <option value="institution">Connected institutions</option>
              <option value="self_uploaded">Self-uploaded</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-800">
              Institution
            </label>
            <select
              aria-label="Institution"
              value={value.institutionId ?? ''}
              onChange={(event) =>
                onChange('institutionId', event.target.value)
              }
              className="h-11 w-full rounded-xl border border-ink-400/30 bg-white px-4 text-sm text-ink-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All institutions</option>
              {institutions.map((institution) => (
                <option key={institution.id} value={institution.id}>
                  {institution.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-800">
              Date from
            </label>
            <Input
              aria-label="Date from"
              type="date"
              value={value.dateFrom ?? ''}
              onChange={(event) => onChange('dateFrom', event.target.value)}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-800">
              Date to
            </label>
            <Input
              aria-label="Date to"
              type="date"
              value={value.dateTo ?? ''}
              onChange={(event) => onChange('dateTo', event.target.value)}
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={onApply}
            isLoading={isLoading}
          >
            Apply filters
          </Button>
        </div>
      </div>
    </div>
  );
}
