import { OtherMedicationCard } from './OtherMedicationCard.tsx';
import { useEffect, useState } from 'react';
import type {
  Institution,
  InstitutionConnection,
  OtherMedicalInfo,
} from '../../../api/types.ts';
import { datasetApi } from '../../../api';

function OtherMedications() {
  const [medicalInfo, setMedicalInfo] = useState<OtherMedicalInfo[]>([]);
  const [institutionConnections, setInstitutionConnections] = useState<
    InstitutionConnection[]
  >([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);

  useEffect(() => {
    const loadData = async () => {
      const [medicalInfoData, connectionsData, institutionsData] =
        await Promise.all([
          datasetApi.getOtherMedicalInfo('user-001'),
          datasetApi.getInstitutionConnections('user-001'),
          datasetApi.getInstitutions(),
        ]);
      setMedicalInfo(medicalInfoData);
      setInstitutionConnections(connectionsData);
      setInstitutions(institutionsData);
    };
    loadData();
  }, []);

  return (
    <div className="flex gap-2 mx-10">
      {' '}
      {medicalInfo.map((info) => (
        <OtherMedicationCard
          key={info.id}
          medicalInfo={info}
          institutions={institutions}
          institutionConnections={institutionConnections}
        />
      ))}{' '}
    </div>
  );
}

export default OtherMedications;
