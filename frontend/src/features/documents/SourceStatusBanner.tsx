import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { SourceState } from '../../api/types.ts';
import { Button } from '../../components/Button.tsx';
import type { RecordTab } from '../../lib/recipientAccess.ts';
import { useDatasetStore } from '../../store/datasetStore.ts';

const PROBLEM: Record<Exclude<SourceState, 'ok'>, string> = {
  timeout: "didn't respond in time",
  unavailable: 'is unavailable right now',
  unauthorised: 'needs its access renewed',
  needs_reconnect: 'must be removed and added again to include this category',
};

// Retrying cannot fix these; the owner has to reconnect on the Institutions page.
const NEEDS_RECONNECT: SourceState[] = ['unauthorised', 'needs_reconnect'];

const describe = (status: SourceState) =>
  PROBLEM[status as Exclude<SourceState, 'ok'>] ?? "couldn't be reached";

/**
 * Tells the user which institutions the list is built from. A slow or failing
 * institution only affects its own rows, so the rest still show; this says what is
 * missing instead of letting it pass as "no records".
 */
export function SourceStatusBanner({ tab }: { tab: RecordTab }) {
  const sources = useDatasetStore((state) => state.sources[tab]);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const loadCategory = useDatasetStore((state) => state.loadCategory);
  // A caregiver can't reconnect someone else's institution.
  const isOwnVault = useDatasetStore((state) => state.activeRecipient === null);

  if (sources.length === 0) return null;
  const failed = sources.filter((s) => s.status !== 'ok');
  const okCount = sources.length - failed.length;

  if (failed.length === 0) {
    return (
      <p className="mb-4 text-sm text-ink-600" role="status">
        Showing data from {okCount} of {sources.length} institution
        {sources.length === 1 ? '' : 's'}.
      </p>
    );
  }

  return (
    <div
      role="status"
      className="mb-4 flex items-start gap-3 rounded-card border border-coral-500/30 bg-coral-500/5 p-4"
    >
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-coral-500" />
      <div className="min-w-0 flex-1 text-sm text-ink-900">
        <p className="font-medium">
          Showing data from {okCount} of {sources.length} institution
          {sources.length === 1 ? '' : 's'}.
        </p>
        <ul className="mt-1 text-ink-600">
          {failed.map((s) => (
            <li key={s.institutionId}>
              {s.institution} {describe(s.status)}.
            </li>
          ))}
        </ul>
      </div>
      <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
        {failed.some((s) => !NEEDS_RECONNECT.includes(s.status)) && (
          <Button
            variant="outline"
            size="sm"
            disabled={isLoading}
            onClick={() => void loadCategory(tab)}
          >
            Retry
          </Button>
        )}
        {isOwnVault && failed.some((s) => NEEDS_RECONNECT.includes(s.status)) && (
          <Link
            to="/institutions"
            className="inline-flex h-9 items-center rounded-xl border border-primary-500 px-3 text-sm font-medium text-primary-600 hover:bg-primary-50"
          >
            Manage institutions
          </Link>
        )}
      </div>
    </div>
  );
}
