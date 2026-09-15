import { Card } from '../../../components/Card';
import { Badge } from '../../../components/Badge';
import type {
  OtherMedicalInfo,
  Institution,
  InstitutionConnection,
} from '../../../api/types';
interface MedicalInfoCardProps {
  medicalInfo: OtherMedicalInfo;
  institutions: Institution[];
  institutionConnections: InstitutionConnection[];
}
function formatFieldType(fieldType: string) {
  return fieldType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
export function OtherMedicationCard({
  medicalInfo,
  institutions,
  institutionConnections,
}: MedicalInfoCardProps) {
  const connection = institutionConnections.find(
    (connection) => connection.id === medicalInfo.institution_connection_id
  );
  const institution = institutions.find(
    (institution) => institution.id === connection?.institution_id
  );
  return (
    <Card
      interactive
      onClick={() =>
        console.log(`Selected medical info: ${medicalInfo.field_type}`)
      }
      className="flex-1"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="font-sans text-sm font-medium text-ink-400">
            {formatFieldType(medicalInfo.field_type)}
          </p>
          <p className="font-sans text-base font-medium text-ink-900">
            {medicalInfo.field_value}
          </p>
        </div>
        <Badge variant="neutral">
          {institution?.name ?? 'Unknown institution'}
        </Badge>
      </div>
    </Card>
  );
}
