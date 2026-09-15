import { DiagnosticCard } from './DiagnosticCard.tsx';
import { useDatasetStore } from '../../../store/datasetStore.ts';

function Diagnostics() {
  const diagnostics = useDatasetStore((state) => state.diagnostics);
  const institutionConnections = useDatasetStore(
    (state) => state.institutionConnections
  );
  const institutions = useDatasetStore((state) => state.institutions);

  return (
    <div className="grid gap-4 px-4 py-6 sm:px-6 md:grid-cols-2 lg:px-10 xl:grid-cols-3">
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
