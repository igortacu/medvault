import CertificateCard from './CertificateCard';
import { useDatasetStore } from '../../../store/datasetStore.ts';

function Certificates() {
  const certificates = useDatasetStore((state) => state.certificates);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  const institutions = useDatasetStore((state) => state.institutions);

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
