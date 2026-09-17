import { useState } from 'react';
import { Badge } from '../../../components/Badge.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';

function Certificates() {
  const certificates = useDatasetStore((state) => state.certificates);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  if (certificates.length === 0) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <EmptyState
          icon={<FileX size={32} />}
          title="No certificates yet"
          description="Certificates added by connected institutions or uploaded by you will appear here."
        />
      </div>
    );
  }
  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
      {certificates.map((certificate) => (
        <DocumentsCard
          key={certificate.id}
          title={certificate.title}
          type={certificate.type}
          subtitle={
            certificate.date ? `Issued ${formatDate(certificate.date)}` : undefined
          }
          institution={certificate.sourceLabel}
          badges={
            certificate.status && (
              <Badge
                variant={certificate.status === 'stored' ? 'success' : 'danger'}
              >
                {certificate.status === 'stored' ? 'Stored' : 'Rejected'}
              </Badge>
            )
          }
          onClick={() => setSelected(certificate)}
        />
      ))}

      <RecordDetailModal
        record={selected}
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}

export default Certificates;
