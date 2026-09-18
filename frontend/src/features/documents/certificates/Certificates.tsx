import { useState } from 'react';
import { Badge } from '../../../components/Badge.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';
import DocumentsFilterBar from '../DocumentFilterBar.tsx';

function Certificates() {
  const certificates = useDatasetStore((state) => state.certificates);
  const filters = useDatasetStore((state) => state.filters.certificates);
  const institutions = useDatasetStore((state) => state.institutions);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const setFilters = useDatasetStore((state) => state.setFilters);
  const loadCategory = useDatasetStore((state) => state.loadCategory);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  const applyFilters = (nextFilters: typeof filters) => {
    setFilters('certificates', nextFilters);
    void loadCategory('certificates');
  };

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <DocumentsFilterBar
        records={certificates}
        institutions={institutions}
        value={filters}
        isLoading={isLoading}
        onChange={applyFilters}
      />
      {certificates.length === 0 ? (
        <EmptyState
          icon={<FileX size={32} />}
          title={
            Object.values(filters).some(Boolean)
              ? 'No matching certificates'
              : 'No certificates yet'
          }
          description={
            Object.values(filters).some(Boolean)
              ? 'No certificates match the selected filters.'
              : 'Certificates added by connected institutions or uploaded by you will appear here.'
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {certificates.map((certificate) => (
            <DocumentsCard
              key={certificate.id}
              title={certificate.title}
              type={certificate.type}
              subtitle={
                certificate.date
                  ? `Issued ${formatDate(certificate.date)}`
                  : undefined
              }
              institution={certificate.sourceLabel}
              badges={
                certificate.status && (
                  <Badge
                    variant={
                      certificate.status === 'stored' ? 'success' : 'danger'
                    }
                  >
                    {certificate.status === 'stored' ? 'Stored' : 'Rejected'}
                  </Badge>
                )
              }
              onClick={() => setSelected(certificate)}
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

export default Certificates;
