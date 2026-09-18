import { Search, SlidersHorizontal, X } from 'lucide-react';
import { useState } from 'react';
import { Button } from '../../components/Button.tsx';
import { Input } from '../../components/Input.tsx';
import type {
  Institution,
  MedicalRecord,
  MedicalRecordFilters,
} from '../../api/types.ts';
import { DocumentsFilterModal } from './DocumentsFilterModal.tsx';
interface DocumentsFilterBarProps {
  records: MedicalRecord[];
  institutions: Institution[];
  value: MedicalRecordFilters;
  isLoading?: boolean;
  onChange: (filters: MedicalRecordFilters) => void;
}
const emptyFilters: MedicalRecordFilters = {};
function hasActiveFilters(filters: MedicalRecordFilters) {
  return Object.values(filters).some(Boolean);
}
export function DocumentsFilterBar({
  records,
  institutions,
  value,
  isLoading = false,
  onChange,
}: DocumentsFilterBarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState<MedicalRecordFilters>(value);
  const updateDraft = <K extends keyof MedicalRecordFilters>(
    key: K,
    nextValue: MedicalRecordFilters[K]
  ) => {
    setDraft((current) => ({
      ...current,
      [key]: nextValue || undefined,
    }));
  };
  const applyFilters = () => {
    onChange(draft);
    setIsOpen(false);
  };
  const clearFilters = () => {
    setDraft(emptyFilters);
    onChange(emptyFilters);
  };
  const handleSearchChange = (search: string) => {
    const nextFilters = { ...value, search: search || undefined };
    onChange(nextFilters);
    setDraft(nextFilters);
  };
  return (
    <>
      <div className="relative mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-start">
        <Input
          aria-label="Search documents"
          placeholder="Search by title"
          value={value.search ?? ''}
          leftIcon={<Search size={16} />}
          onChange={(event) => handleSearchChange(event.target.value)}
          className="order-1 w-full sm:order-2 sm:w-[450px] sm:max-w-[450px]"
        />
        <div className="order-2 flex items-center gap-2 sm:order-1">
          <Button
            type="button"
            size="default"
            variant="outline"
            onClick={() => setIsOpen((open) => !open)}
          >
            <SlidersHorizontal size={16} aria-hidden="true" /> Filters
          </Button>
          {hasActiveFilters(value) && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={clearFilters}
              disabled={isLoading}
            >
              <X size={14} aria-hidden="true" /> Clear{' '}
            </Button>
          )}
        </div>
        {isOpen && (
          <DocumentsFilterModal
            records={records}
            institutions={institutions}
            value={draft}
            isLoading={isLoading}
            onChange={updateDraft}
            onApply={applyFilters}
            onClose={() => setIsOpen(false)}
          />
        )}
      </div>
    </>
  );
}

export default DocumentsFilterBar;
