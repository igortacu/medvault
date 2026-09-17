import { useState } from 'react';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import { formatDate } from '../../../utils/formatDate.ts';
import type { MedicalRecord } from '../../../api/types.ts';

function MedicalInfo() {
  const medicalInfos = useDatasetStore((state) => state.otherMedicalInfo);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  if (medicalInfos.length === 0) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <EmptyState
          icon={<FileX size={32} />}
          title="No medical information yet"
          description="Medical infomation added by connected institutions or uploaded by you will appear here."
        />
      </div>
    );
  }
  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
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

      <RecordDetailModal
        record={selected}
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}

export default MedicalInfo;
