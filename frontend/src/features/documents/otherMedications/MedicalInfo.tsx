import { MedicalInfoCard } from './MedicalInfoCard.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';

function MedicalInfo() {
  const medicalInfo = useDatasetStore((state) => state.otherMedicalInfo);
  const institutions = useDatasetStore((state) => state.institutions);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  return (
    <div className="flex gap-2 mx-10">
      {' '}
      {medicalInfo.map((info) => (
        <MedicalInfoCard
          key={info.id}
          medicalInfo={info}
          institutions={institutions}
          institutionConnections={institutionConnections}
        />
      ))}{' '}
    </div>
  );
}

export default MedicalInfo;
