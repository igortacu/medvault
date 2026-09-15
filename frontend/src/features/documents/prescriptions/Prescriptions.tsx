import { PrescriptionCard } from './PrescriptionCard.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';
function Prescriptions() {
  const prescriptions = useDatasetStore((state) => state.prescriptions);
  const institutions = useDatasetStore((state) => state.institutions);
  const hospitalConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
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
