import CertificateCard from './CertificateCard';
import { useDatasetStore } from '../../../store/datasetStore.ts';

function Certificates() {
  const certificates = useDatasetStore((state) => state.certificates);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  const institutions = useDatasetStore((state) => state.institutions);

  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
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
