import { datasetApi } from '../../../api';
import { DiagnosticCard } from './DiagnosticCard.tsx';
import { useEffect, useState } from 'react';
import type {
  Diagnostic,
  Institution,
  InstitutionConnection,
} from '../../../api/types.ts';

function Diagnostics() {
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [hospitalConnections, setHospitalConnections] = useState<
    InstitutionConnection[]
  >([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);

  useEffect(() => {
    const loadData = async () => {
      const [diagnosticsData, connectionsData, institutionsData] =
        await Promise.all([
          datasetApi.getDiagnostics('user-001'),
          datasetApi.getInstitutionConnections('user-001'),
          datasetApi.getInstitutions(),
        ]);
      setDiagnostics(diagnosticsData);
      setHospitalConnections(connectionsData);
      setInstitutions(institutionsData);
    };
    loadData();
  }, []);

  return (
    <div className="flex gap-2 mx-10">
      {diagnostics.map((diagnostic) => (
        <DiagnosticCard
          key={diagnostic.id}
          diagnostic={diagnostic}
          hospitalConnections={hospitalConnections}
          institutions={institutions}
        />
      ))}
    </div>
  );
}

export default Diagnostics;
