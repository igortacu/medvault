// import { useNavigate } from 'react-router-dom';
import { Card } from '../../../components/Card';
import { Badge } from '../../../components/Badge';
import type {
  Diagnostic,
  Institution,
  InstitutionConnection,
} from '../../../api/types';
import { formatDate } from '../../../utils/formatDate.ts';

interface DiagnosticCardProps {
  diagnostic: Diagnostic;
  institutionConnection: InstitutionConnection[];
  institutions: Institution[];
}

export function DiagnosticCard({
  diagnostic,
  institutionConnection,
  institutions,
}: DiagnosticCardProps) {
  // const navigate = useNavigate();
  const connection = institutionConnection.find(
    (connection) => connection.id === diagnostic.institution_connection_id
  );
  const institution = institutions.find(
    (institution) => institution.id === connection?.institution_id
  );

  return (
    <Card
      interactive
      onClick={() =>
        console.log(`Sent to ` + diagnostic.diagnostic_name + ' diagnostic')
      }
      className="h-full"
    >
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-sans text-sm font-medium text-ink-900">
            {diagnostic.diagnostic_name}
          </p>

          <p className="text-sm text-ink-400">
            {formatDate(diagnostic.record_date)} ·
          </p>
        </div>

        <Badge variant="neutral">{institution?.name}</Badge>
      </div>
    </Card>
  );
}
