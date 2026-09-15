import { Badge } from '../../../components/Badge';
import { Card } from '../../../components/Card';
import type {
  Prescription,
  Institution,
  InstitutionConnection,
} from '../../../api/types';
interface PrescriptionCardProps {
  prescription: Prescription;
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];
}
export function PrescriptionCard({
  prescription,
  institutions,
  institutionConnections,
}: PrescriptionCardProps) {
  const connection = institutionConnections.find(
    (connection) => connection.id === prescription.institution_connection_id
  );
  const institution = institutions.find(
    (institution) => institution.id === connection?.institution_id
  );
  return (
    <Card
      interactive
      onClick={() =>
        console.log(`Selected prescription: ${prescription.medication_name}`)
      }
      className="flex-1"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="font-sans text-sm font-medium text-ink-900">
            {prescription.medication_name}{' '}
          </p>
          <p className="text-sm text-ink-400">
            {institution?.name ?? 'Unknown institution'}{' '}
          </p>
        </div>
        <Badge
          variant={prescription.status === 'active' ? 'success' : 'neutral'}
        >
          {prescription.status}
        </Badge>
      </div>
    </Card>
  );
}
