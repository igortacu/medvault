import { DiagnosticCard } from './DiagnosticCard.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';

function Diagnostics() {
  const diagnostics = useDatasetStore((state) => state.diagnostics);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  const institutions = useDatasetStore((state) => state.institutions);

  return (
    <div className="flex gap-2 mx-10">
      {diagnostics.map((diagnostic) => (
        <DiagnosticCard
          key={diagnostic.id}
          diagnostic={diagnostic}
          institutionConnection={institutionConnections}
          institutions={institutions}
        />
      ))}
    </div>
  );
}

export default Diagnostics;
