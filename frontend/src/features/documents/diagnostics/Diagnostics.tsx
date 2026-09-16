import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import { formatDate } from '../../../utils/formatDate.ts';
import DocumentsCard from '../DocumentsCard.tsx';

function Diagnostics() {
  const diagnostics = useDatasetStore((state) => state.diagnostics);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  const institutions = useDatasetStore((state) => state.institutions);
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
      {diagnostics.map((diagnostic) => {
        const connection = institutionConnections.find(
          (connection) => connection.id === diagnostic.institution_connection_id
        );
        const institution = institutions.find(
          (institution) => institution.id === connection?.institution_id
        );

        return (<DocumentsCard
          title={diagnostic.diagnostic_name}
          subtitle={formatDate(diagnostic.record_date)}
          institution={institution?.name ?? 'Unknown institution'}
          onClick={() =>
            console.log(`Selected diagnostic: ${diagnostic.diagnostic_name}`)
          }
        />);
      })}
    </div>
  );
}

export default Diagnostics;
