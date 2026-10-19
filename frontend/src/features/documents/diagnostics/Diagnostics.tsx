import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import { formatDate } from '../../../utils/formatDate.ts';
import { SourceStatusBanner } from '../SourceStatusBanner.tsx';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import type { MedicalRecord } from '../../../api/types.ts';
import DocumentsFilterBar from '../DocumentFilterBar.tsx';
import { recordSource, recordTitle, recordTypeLabel } from '../recordLabels.ts';

function Diagnostics() {
  const { t } = useTranslation('documents');
  const diagnostics = useDatasetStore((state) => state.diagnostics);
  const filters = useDatasetStore((state) => state.filters.diagnostics);
  const institutions = useDatasetStore((state) => state.institutions);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const setFilters = useDatasetStore((state) => state.setFilters);
  const loadCategory = useDatasetStore((state) => state.loadCategory);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  const applyFilters = (nextFilters: typeof filters) => {
    setFilters('diagnostics', nextFilters);
    void loadCategory('diagnostics');
  };

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <SourceStatusBanner tab="diagnostics" />
      <DocumentsFilterBar
        records={diagnostics}
        institutions={institutions}
        value={filters}
        isLoading={isLoading}
        onChange={applyFilters}
      />
      {diagnostics.length === 0 ? (
        <EmptyState
          icon={<FileX size={32} />}
          title={
            Object.values(filters).some(Boolean)
              ? t('empty.diagnostics.filteredTitle')
              : t('empty.diagnostics.title')
          }
          description={
            Object.values(filters).some(Boolean)
              ? t('empty.diagnostics.filteredDescription')
              : t('empty.diagnostics.description')
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {diagnostics.map((diagnostic) => (
            <DocumentsCard
              key={diagnostic.id}
              title={recordTitle(diagnostic)}
              type={recordTypeLabel(diagnostic)}
              subtitle={
                diagnostic.date ? formatDate(diagnostic.date) : undefined
              }
              institution={recordSource(diagnostic)}
              onClick={() => setSelected(diagnostic)}
            />
          ))}
        </div>
      )}

      <RecordDetailModal
        record={selected}
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}

export default Diagnostics;
