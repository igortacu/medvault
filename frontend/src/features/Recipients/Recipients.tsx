import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDatasetStore } from '../../store/datasetStore';
import { useCaregiverStore } from '../../store/caregiverStore';
import { EmptyState } from '../../components/EmptyState';
import { SkeletonListItem } from '../../components/Skeleton';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { useToast } from '../../components/Toast';
import { RecipientCard } from './RecipientCard';
import { useSwitchToSelf } from './useSwitchToSelf';
import { firstAllowedPath } from '../../lib/recipientAccess';
import type { CareRecipient } from '../../api/caregiver.types';

function Recipients() {
  const { t } = useTranslation(['caregiver', 'common']);
  const currentUser = useDatasetStore((state) => state.currentUser);
  const allRecipients = useCaregiverStore((state) => state.usersICareFor);
  const usersICareFor = allRecipients.filter((r) => r.status === 'active');
  const isLoading = useCaregiverStore((state) => state.isLoading);
  const loadUsersICareFor = useCaregiverStore(
    (state) => state.loadUsersICareFor
  );
  const respondToCaregiverRequest = useCaregiverStore(
    (state) => state.respondToCaregiverRequest
  );
  const activeRecipient = useDatasetStore((state) => state.activeRecipient);
  const switchToRecipient = useDatasetStore((state) => state.switchToRecipient);
  const switchToSelf = useDatasetStore((state) => state.switchToSelf);
  const switchBack = useSwitchToSelf();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [recipientToReject, setRecipientToReject] =
    useState<CareRecipient | null>(null);
  const [isRejecting, setIsRejecting] = useState(false);

  useEffect(() => {
    if (currentUser) loadUsersICareFor(currentUser.id);
  }, [currentUser, loadUsersICareFor]);

  async function handleConfirmReject() {
    if (!recipientToReject) return;
    setIsRejecting(true);
    await respondToCaregiverRequest({
      linkId: recipientToReject.linkId,
      accept: false,
    });
    setIsRejecting(false);

    // The store swallows errors into `error` rather than rethrowing.
    if (useCaregiverStore.getState().error) {
      showToast({
        variant: 'error',
        title: t('recipients.stopFailed'),
        description: t('common:pleaseTryAgain'),
      });
      return;
    }
    // Their vault is closed to us now, so don't stay inside it.
    if (recipientToReject.linkId === activeRecipient?.linkId) {
      void switchToSelf();
    }
    showToast({
      variant: 'success',
      title: t('recipients.stopped', { name: recipientToReject.name }),
    });
    setRecipientToReject(null);
  }

  function handleSwitch(recipient: CareRecipient) {
    void switchToRecipient(recipient);
    navigate(firstAllowedPath(recipient));
  }

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <h1 className="font-display text-xl font-semibold text-ink-900">
        {t('recipients.title')}
      </h1>
      <p className="mt-1 text-sm text-ink-400">{t('recipients.subtitle')}</p>

      <div className="mt-6 space-y-3">
        {isLoading && usersICareFor.length === 0 && (
          <>
            <SkeletonListItem />
            <SkeletonListItem />
          </>
        )}

        {!isLoading && usersICareFor.length === 0 && (
          <EmptyState
            icon={<Users size={32} />}
            title={t('recipients.emptyTitle')}
            description={t('recipients.emptyDescription')}
          />
        )}

        {usersICareFor.map((recipient) => (
          <RecipientCard
            key={recipient.linkId}
            recipient={recipient}
            onReject={setRecipientToReject}
            onSwitch={handleSwitch}
            onSwitchBack={switchBack}
            isActive={recipient.linkId === activeRecipient?.linkId}
          />
        ))}
      </div>

      <ConfirmDialog
        open={recipientToReject !== null}
        onOpenChange={(open) => {
          if (!open && !isRejecting) setRecipientToReject(null);
        }}
        title={t('recipients.confirmTitle', {
          name: recipientToReject?.name ?? '',
        })}
        description={t('recipients.confirmDescription')}
        confirmLabel={t('recipients.reject')}
        variant="danger"
        isLoading={isRejecting}
        onConfirm={handleConfirmReject}
      />
    </div>
  );
}

export default Recipients;
