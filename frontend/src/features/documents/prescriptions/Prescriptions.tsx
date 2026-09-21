import { useState } from 'react';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';
import DocumentsFilterBar from '../DocumentFilterBar.tsx';

function Prescriptions() {
  const prescriptions = useDatasetStore((state) => state.prescriptions);
  const filters = useDatasetStore((state) => state.filters.prescriptions);
  const institutions = useDatasetStore((state) => state.institutions);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const setFilters = useDatasetStore((state) => state.setFilters);
  const loadCategory = useDatasetStore((state) => state.loadCategory);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  const applyFilters = (nextFilters: typeof filters) => {
    setFilters('prescriptions', nextFilters);
    void loadCategory('prescriptions');
  };

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <DocumentsFilterBar
        records={prescriptions}
        institutions={institutions}
        value={filters}
        isLoading={isLoading}
        onChange={applyFilters}
      />
      {prescriptions.length === 0 ? (
        <EmptyState
          icon={<FileX size={32} />}
          title={
            Object.values(filters).some(Boolean)
              ? 'No matching prescriptions'
              : 'No prescriptions yet'
          }
          description={
            Object.values(filters).some(Boolean)
              ? 'No prescriptions match the selected filters.'
              : 'Prescriptions added by connected institutions or uploaded by you will appear here.'
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {prescriptions.map((prescription) => (
            <DocumentsCard
              key={prescription.id}
              title={prescription.title}
              type={prescription.type}
              subtitle={
                prescription.date ? formatDate(prescription.date) : undefined
              }
              institution={prescription.sourceLabel}
              onClick={() => setSelected(prescription)}
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

export default Prescriptions;
