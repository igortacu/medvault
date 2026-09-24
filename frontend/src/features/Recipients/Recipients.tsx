import { useEffect } from 'react';
import { Users } from 'lucide-react';
import { useDatasetStore } from '../../store/datasetStore';
import { useCaregiverStore } from '../../store/caregiverStore';
import { Card } from '../../components/Card';
import { Avatar } from '../../components/Avatar';
import { Badge } from '../../components/Badge';
import { EmptyState } from '../../components/EmptyState';
import { SkeletonListItem } from '../../components/Skeleton';
import type { CaregiverLinkStatus } from '../../api/caregiver.types';

const STATUS_VARIANT: Record<
  CaregiverLinkStatus,
  'success' | 'warning' | 'danger'
> = {
  active: 'success',
  pending: 'warning',
  rejected: 'danger',
  revoked: 'danger',
};

function Recipients() {
  const currentUser = useDatasetStore((state) => state.currentUser);
  const allRecipients = useCaregiverStore((state) => state.usersICareFor);
  const usersICareFor = allRecipients.filter((r) => r.status !== 'pending');
  const isLoading = useCaregiverStore((state) => state.isLoading);
  const loadUsersICareFor = useCaregiverStore(
    (state) => state.loadUsersICareFor
  );

  useEffect(() => {
    if (currentUser) loadUsersICareFor(currentUser.id);
  }, [currentUser, loadUsersICareFor]);

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
          <Card key={recipient.linkId} className="flex items-center gap-4">
            <Avatar name={recipient.name} />
            <div className="min-w-0">
              <p className="truncate font-sans text-sm font-medium text-ink-900">
                {recipient.name}
              </p>
              <p className="text-sm text-ink-400">
                {recipient.permissions.filter((p) => p.granted).length} of{' '}
                {recipient.permissions.length} categories shared
              </p>
            </div>
            <Badge
              variant={STATUS_VARIANT[recipient.status]}
              className="ml-auto"
            >
              {recipient.status}
            </Badge>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default Recipients;
