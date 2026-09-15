import { Card } from '../../../components/Card';
import { Badge } from '../../../components/Badge';
import type {
  Certificate,
  Institution,
  InstitutionConnection,
} from '../../../api/types';
import { formatDate } from '../../../utils/formatDate';
interface CertificateCardProps {
  certificate: Certificate;
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];
}
function CertificateCard({
  certificate,
  institutions,
  institutionConnections,
}: CertificateCardProps) {
  const connection = institutionConnections.find(
    (connection) => connection.id === certificate.institution_connection_id
  );
  const institution = institutions.find(
    (institution) => institution.id === connection?.institution_id
  );
  return (
    <Card
      interactive
      onClick={() => console.log(`Selected certificate: ${certificate.id}`)}
      className="h-full"
    >
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-sans text-sm font-medium text-ink-900">
            Medical Certificate
          </p>
          <p className="text-sm text-ink-400">
            Issued {formatDate(certificate.issue_date)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1 sm:flex-col sm:items-end">
          <Badge variant="neutral">
            {institution?.name ?? 'Unknown institutions'}
          </Badge>
          <Badge
            variant={certificate.visible_to_caregiver ? 'success' : 'neutral'}
          >
            {certificate.visible_to_caregiver
              ? 'Visible to caregiver'
              : 'Private'}
          </Badge>
        </div>
      </div>
    </Card>
  );
}

export default CertificateCard;
