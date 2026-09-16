import { Badge } from '../../../components/Badge.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';
import { EmptyState } from '../../../components/EmptyState.tsx';
import { FileX } from 'lucide-react';
import DocumentsCard from '../DocumentsCard.tsx';
import { formatDate } from '../../../utils/formatDate.ts';

function Certificates() {
  const certificates = useDatasetStore((state) => state.certificates);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  const institutions = useDatasetStore((state) => state.institutions);
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
      {certificates.map((certificate) => {
        const connection = institutionConnections.find(
          (connection) =>
            connection.id === certificate.institution_connection_id
        );
        const institution = institutions.find(
          (institution) => institution.id === connection?.institution_id
        );

        return (
          <DocumentsCard
            key={certificate.id}
            title="Medical Certificate"
            subtitle={`Issued ${formatDate(certificate.issue_date)}`}
            institution={institution?.name ?? 'Unknown institution'}
            badges={
              <Badge
                variant={
                  certificate.visible_to_caregiver ? 'success' : 'neutral'
                }
              >
                {certificate.visible_to_caregiver
                  ? 'Visible to caregiver'
                  : 'Private'}
              </Badge>
            }
            onClick={() =>
              console.log(`Selected certificate: ${certificate.id}`)
            }
          />
        );
      })}
    </div>
  );
}

export default Certificates;
