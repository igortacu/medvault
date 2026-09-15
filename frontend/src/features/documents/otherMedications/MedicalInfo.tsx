import { MedicalInfoCard } from './MedicalInfoCard.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';

function MedicalInfo() {
  const medicalInfo = useDatasetStore((state) => state.otherMedicalInfo);
  const institutions = useDatasetStore((state) => state.institutions);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
      {medicalInfo.map((info) => (
        <MedicalInfoCard
          key={info.id}
          medicalInfo={info}
          institutions={institutions}
          institutionConnections={institutionConnections}
        />
      ))}
    </div>
  );
}

export default MedicalInfo;
