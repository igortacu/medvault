import { PrescriptionCard } from './PrescriptionCard.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';
function Prescriptions() {
  const prescriptions = useDatasetStore((state) => state.prescriptions);
  const institutions = useDatasetStore((state) => state.institutions);
  const hospitalConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
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
