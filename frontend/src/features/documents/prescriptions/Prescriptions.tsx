import { useEffect, useState } from 'react';
import type {
  Prescription,
  Institution,
  InstitutionConnection,
} from '../../../api/types.ts';
import { datasetApi } from '../../../api';
import { PrescriptionCard } from './PrescriptionCard.tsx';
function Prescriptions() {
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [hospitalConnections, setHospitalConnections] = useState<
    InstitutionConnection[]
  >([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);

  useEffect(() => {
    const loadData = async () => {
      const [prescriptionData, connectionsData, institutionsData] =
        await Promise.all([
          datasetApi.getPrescriptions('user-001'),
          datasetApi.getInstitutionConnections('user-001'),
          datasetApi.getInstitutions(),
        ]);
      setPrescriptions(prescriptionData);
      setHospitalConnections(connectionsData);
      setInstitutions(institutionsData);
    };
    loadData();
  }, []);
  return (
    <div className="flex gap-2 mx-10">
      {prescriptions.map((prescription) => (
        <PrescriptionCard
          key={prescription.id}
          prescription={prescription}
          institutions={institutions}
          institutionConnections={hospitalConnections}
        />
      ))}
    </div>
  );
}

export default Prescriptions;
