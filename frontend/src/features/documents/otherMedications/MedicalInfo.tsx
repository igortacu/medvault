import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import { SourceStatusBanner } from '../SourceStatusBanner.tsx';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';
import DocumentsFilterBar from '../DocumentFilterBar.tsx';
import { recordSource, recordTitle, recordTypeLabel } from '../recordLabels.ts';

function MedicalInfo() {
  const { t } = useTranslation('documents');
  const medicalInfos = useDatasetStore((state) => state.otherMedicalInfo);
  const filters = useDatasetStore((state) => state.filters.otherMedicalInfo);
  const institutions = useDatasetStore((state) => state.institutions);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const setFilters = useDatasetStore((state) => state.setFilters);
  const loadCategory = useDatasetStore((state) => state.loadCategory);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  const applyFilters = (nextFilters: typeof filters) => {
    setFilters('otherMedicalInfo', nextFilters);
    void loadCategory('otherMedicalInfo');
  };

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <SourceStatusBanner tab="otherMedicalInfo" />
      <DocumentsFilterBar
        records={medicalInfos}
        institutions={institutions}
        value={filters}
        isLoading={isLoading}
        onChange={applyFilters}
      />
      {medicalInfos.length === 0 ? (
        <EmptyState
          icon={<FileX size={32} />}
          title={
            Object.values(filters).some(Boolean)
              ? t('empty.otherMedicalInfo.filteredTitle')
              : t('empty.otherMedicalInfo.title')
          }
          description={
            Object.values(filters).some(Boolean)
              ? t('empty.otherMedicalInfo.filteredDescription')
              : t('empty.otherMedicalInfo.description')
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {medicalInfos.map((medicalInfo) => (
            <DocumentsCard
              key={medicalInfo.id}
              title={recordTitle(medicalInfo)}
              type={recordTypeLabel(medicalInfo)}
              subtitle={
                medicalInfo.date ? formatDate(medicalInfo.date) : undefined
              }
              institution={recordSource(medicalInfo)}
              onClick={() => setSelected(medicalInfo)}
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

export default MedicalInfo;
