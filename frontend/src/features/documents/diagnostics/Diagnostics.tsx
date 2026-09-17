import { useState } from 'react';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import { formatDate } from '../../../utils/formatDate.ts';
import DocumentsCard from '../DocumentsCard.tsx';
import { RecordDetailModal } from '../RecordDetailModal.tsx';
import type { MedicalRecord } from '../../../api/types.ts';

function Diagnostics() {
  const diagnostics = useDatasetStore((state) => state.diagnostics);
  const [selected, setSelected] = useState<MedicalRecord | null>(null);

  if (diagnostics.length === 0) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <EmptyState
          icon={<FileX size={32} />}
          title="No diagnostics yet"
          description="Diagnostics added by connected institutions or uploaded by you will appear here."
        />
      </div>
    );
  }

  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
      {diagnostics.map((diagnostic) => (
        <DocumentsCard
          key={diagnostic.id}
          title={diagnostic.title}
          type={diagnostic.type}
          subtitle={diagnostic.date ? formatDate(diagnostic.date) : undefined}
          institution={diagnostic.sourceLabel}
          onClick={() => setSelected(diagnostic)}
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

export default Diagnostics;
