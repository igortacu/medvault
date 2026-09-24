import type { ReactNode } from 'react';
import { Lock } from 'lucide-react';
import { useDatasetStore } from '../../store/datasetStore';
import { EmptyState } from '../../components/EmptyState';
import { Button } from '../../components/Button';
import { canViewTab, type RecordTab } from '../../lib/recipientAccess';
import { useSwitchToSelf } from './useSwitchToSelf';

export type RecipientGateProps =
  | { tab: RecordTab; children: ReactNode }
  | { ownOnly: true; children: ReactNode };

/**
 * Guards a route while viewing a recipient's vault: record tabs need the
 * matching category granted, and account pages (institutions, caregivers)
 * are only for the user's own vault. Covers direct URLs; the Sidebar hides
 * the same links.
 */
export function RecipientGate(props: RecipientGateProps) {
  const activeRecipient = useDatasetStore((state) => state.activeRecipient);
  const switchBack = useSwitchToSelf();

  if (!activeRecipient) return props.children;
  if ('tab' in props && canViewTab(activeRecipient, props.tab)) {
    return props.children;
  }

  const description =
    'tab' in props
      ? `${activeRecipient.name} hasn't shared this category with you.`
      : 'This page manages your own account. Switch back to your records to use it.';

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <EmptyState
        icon={<Lock size={32} />}
        title="Not available"
        description={description}
        action={
          <Button variant="outline" size="sm" onClick={switchBack}>
            Switch back to my records
          </Button>
        }
      />
    </div>
  );
}
