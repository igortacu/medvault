import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users } from 'lucide-react';
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
        title: 'Failed to stop caregiving',
        description: 'Please try again.',
      });
      return;
    }
    // Their vault is closed to us now, so don't stay inside it.
    if (recipientToReject.linkId === activeRecipient?.linkId) {
      void switchToSelf();
    }
    showToast({
      variant: 'success',
      title: `You're no longer ${recipientToReject.name}'s caregiver`,
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
        Recipients
      </h1>
      <p className="mt-1 text-sm text-ink-400">
        People whose medical records you've been given caregiver access to.
      </p>

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
            title="No recipients yet"
            description="Once a patient grants you caregiver access, they'll appear here."
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
        title={`Stop being ${recipientToReject?.name ?? ''}'s caregiver?`}
        description="You'll lose access to their medical records. They'll need to invite you again to restore it."
        confirmLabel="Reject"
        variant="danger"
        isLoading={isRejecting}
        onConfirm={handleConfirmReject}
      />
    </div>
  );
}

export default Recipients;
