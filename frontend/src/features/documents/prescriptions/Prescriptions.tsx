import { useState } from 'react';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';

function Prescriptions() {
  const prescriptions = useDatasetStore((state) => state.prescriptions);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  if (prescriptions.length === 0) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <EmptyState
          icon={<FileX size={32} />}
          title="No prescriptions yet"
          description="Prescriptions added by connected institutions or uploaded by you will appear here."
        />
      </div>
    );
  }
  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
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

      <RecordDetailModal
        record={selected}
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}

export default Prescriptions;
