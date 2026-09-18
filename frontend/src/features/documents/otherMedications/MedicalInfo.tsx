import { useState } from 'react';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';
import DocumentsFilterBar from '../DocumentFilterBar.tsx';

function MedicalInfo() {
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
              ? 'No matching medical information'
              : 'No medical information yet'
          }
          description={
            Object.values(filters).some(Boolean)
              ? 'No medical information matches the selected filters.'
              : 'Medical information added by connected institutions or uploaded by you will appear here.'
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {medicalInfos.map((medicalInfo) => (
            <DocumentsCard
              key={medicalInfo.id}
              title={medicalInfo.title}
              type={medicalInfo.type}
              subtitle={
                medicalInfo.date ? formatDate(medicalInfo.date) : undefined
              }
              institution={medicalInfo.sourceLabel}
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
