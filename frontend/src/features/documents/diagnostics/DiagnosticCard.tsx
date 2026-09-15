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
  hospitalConnections: InstitutionConnection[];
  institutions: Institution[];
}

export function DiagnosticCard({
  diagnostic,
  hospitalConnections,
  institutions,
}: DiagnosticCardProps) {
  // const navigate = useNavigate();
  const connection = hospitalConnections.find(
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
      className="flex-1"
    >
      <div className="flex items-center justify-between">
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
