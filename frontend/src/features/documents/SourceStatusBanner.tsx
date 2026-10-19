import { AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { SourceState } from '../../api/types.ts';
import { Button } from '../../components/Button.tsx';
import type { RecordTab } from '../../lib/recipientAccess.ts';
import { useDatasetStore } from '../../store/datasetStore.ts';

const PROBLEMS: SourceState[] = [
  'timeout',
  'unavailable',
  'unauthorised',
  'needs_reconnect',
];

// Retrying cannot fix these; the owner has to reconnect on the Institutions page.
const NEEDS_RECONNECT: SourceState[] = ['unauthorised', 'needs_reconnect'];

/**
 * Tells the user which institutions the list is built from. A slow or failing
 * institution only affects its own rows, so the rest still show; this says what is
 * missing instead of letting it pass as "no records".
 */
export function SourceStatusBanner({ tab }: { tab: RecordTab }) {
  const { t } = useTranslation('documents');
  const sources = useDatasetStore((state) => state.sources[tab]);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const loadCategory = useDatasetStore((state) => state.loadCategory);
  // A caregiver can't reconnect someone else's institution.
  const isOwnVault = useDatasetStore((state) => state.activeRecipient === null);

  if (sources.length === 0) return null;
  const failed = sources.filter((s) => s.status !== 'ok');
  const okCount = sources.length - failed.length;
  const showing = t('sources.showing', {
    ok: okCount,
    count: sources.length,
  });
  const describe = (s: (typeof failed)[number]) =>
    PROBLEMS.includes(s.status)
      ? t(`sources.${s.status as Exclude<SourceState, 'ok'>}`, {
          institution: s.institution,
        })
      : t('sources.unreachable', { institution: s.institution });

  if (failed.length === 0) {
    return (
      <p className="mb-4 text-sm text-ink-600" role="status">
        {showing}
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
          {showing}
        </p>
        <ul className="mt-1 text-ink-600">
          {failed.map((s) => (
            <li key={s.institutionId}>
              {describe(s)}
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
            {t('sources.retry')}
          </Button>
        )}
        {isOwnVault && failed.some((s) => NEEDS_RECONNECT.includes(s.status)) && (
          <Link
            to="/institutions"
            className="inline-flex h-9 items-center rounded-xl border border-primary-500 px-3 text-sm font-medium text-primary-600 hover:bg-primary-50"
          >
            {t('sources.manage')}
          </Link>
        )}
      </div>
    </div>
  );
}
