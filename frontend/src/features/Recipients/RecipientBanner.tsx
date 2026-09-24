import { ArrowLeftRight, Eye } from 'lucide-react';
import { useDatasetStore } from '../../store/datasetStore';
import { Button } from '../../components/Button';
import { useSwitchToSelf } from './useSwitchToSelf';

/** Pinned above every page while viewing a recipient's vault. */
export function RecipientBanner() {
  const activeRecipient = useDatasetStore((state) => state.activeRecipient);
  const switchBack = useSwitchToSelf();

  if (!activeRecipient) return null;

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 bg-primary-600 px-4 py-2.5 text-white sm:px-6 lg:px-10"
    >
      <p className="flex min-w-0 items-center gap-2 text-sm">
        <Eye size={16} aria-hidden="true" className="shrink-0" />
        <span className="truncate">
          Viewing <strong>{activeRecipient.name}</strong>'s records as their
          caregiver
        </span>
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={switchBack}
        className="border-white text-white hover:bg-white/10 focus-visible:ring-white focus-visible:ring-offset-primary-600"
      >
        <ArrowLeftRight size={16} aria-hidden="true" />
        Switch back
      </Button>
    </div>
  );
}
