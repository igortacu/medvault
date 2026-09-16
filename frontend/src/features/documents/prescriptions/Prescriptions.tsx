import { Badge } from '../../../components/Badge.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
function Prescriptions() {
  const prescriptions = useDatasetStore((state) => state.prescriptions);
  const institutions = useDatasetStore((state) => state.institutions);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
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
      {prescriptions.map((prescription) => {
        const connection = institutionConnections.find(
          (connection) =>
            connection.id === prescription.institution_connection_id
        );
        const institution = institutions.find(
          (institution) => institution.id === connection?.institution_id
        );
        return (
          <DocumentsCard
            key={prescription.id}
            title={prescription.medication_name}
            institution={institution?.name ?? 'Unknown institution'}
            badges={
              <Badge
                variant={
                  prescription.status === 'active' ? 'success' : 'neutral'
                }
              >
                {prescription.status}
              </Badge>
            }
            onClick={() =>
              console.log(
                `Selected prescription: ${prescription.medication_name}`
              )
            }
          />
        );
      })}
    </div>
  );
}

export default Prescriptions;
