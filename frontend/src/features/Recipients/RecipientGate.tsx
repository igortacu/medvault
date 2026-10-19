import type { ReactNode } from 'react';
import { Lock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation(['caregiver', 'common']);
  const activeRecipient = useDatasetStore((state) => state.activeRecipient);
  const switchBack = useSwitchToSelf();

  if (!activeRecipient) return props.children;
  if ('tab' in props && canViewTab(activeRecipient, props.tab)) {
    return props.children;
  }

  const description =
    'tab' in props
      ? t('gate.notShared', { name: activeRecipient.name })
      : t('gate.ownOnly');

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <EmptyState
        icon={<Lock size={32} />}
        title={t('common:notAvailable')}
        description={description}
        action={
          <Button variant="outline" size="sm" onClick={switchBack}>
            {t('gate.switchBack')}
          </Button>
        }
      />
    </div>
  );
}
