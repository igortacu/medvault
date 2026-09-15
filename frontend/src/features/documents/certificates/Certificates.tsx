import CertificateCard from './CertificateCard';
import { useEffect, useState } from 'react';
import type {
  Certificate,
  Institution,
  InstitutionConnection,
} from '../../../api/types.ts';
import { datasetApi } from '../../../api';

function Certificates() {
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [institutionConnections, setInstitutionConnection] = useState<
    InstitutionConnection[]
  >([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  useEffect(() => {
    const loadData = async () => {
      const [certificatesData, connectionsData, institutionsData] =
        await Promise.all([
          datasetApi.getCertificates('user-001'),
          datasetApi.getInstitutionConnections('user-001'),
          datasetApi.getInstitutions(),
        ]);
      setCertificates(certificatesData);
      setInstitutionConnection(connectionsData);
      setInstitutions(institutionsData);
    };
    loadData();
  }, []);
  return (
    <div className="flex gap-2 mx-10">
      {certificates.map((certificate) => (
        <CertificateCard
          key={certificate.id}
          certificate={certificate}
          institutions={institutions}
          institutionConnections={institutionConnections}
        />
      ))}
    </div>
  );
}

export default Certificates;
