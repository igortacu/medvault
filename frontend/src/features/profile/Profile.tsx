import { useDatasetStore } from '../../store/datasetStore.ts';
import { Card } from '../../components/Card.tsx';
import { Avatar } from '../../components/Avatar.tsx';
import { Badge } from '../../components/Badge.tsx';
import { Skeleton } from '../../components/Skeleton.tsx';
import { formatDate } from '../../utils/formatDate.ts';

const STATUS_VARIANT = {
  active: 'success',
  pending_verification: 'warning',
  locked: 'danger',
  disabled: 'danger',
} as const;

function Profile() {
  const currentUser = useDatasetStore((state) => state.currentUser);
  const patientProfile = useDatasetStore((state) => state.patientProfile);
  const isLoading = useDatasetStore((state) => state.isLoading);

  if (isLoading && !currentUser) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <Card className="flex items-center gap-4">
          <Skeleton className="h-14 w-14 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-28" />
          </div>
        </Card>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <Card>
          <p className="text-sm text-ink-400">Unable to load your profile.</p>
        </Card>
      </div>
    );
  }

  const fullName = patientProfile
    ? `${patientProfile.first_name} ${patientProfile.last_name}`
    : currentUser.phone;

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <Card className="flex items-center gap-4">
        <Avatar name={fullName} size="lg" />
        <div>
          <p className="font-sans text-lg font-medium text-ink-900">
            {fullName}
          </p>
          <p className="text-sm text-ink-400">{currentUser.phone}</p>
        </div>
        <Badge variant={STATUS_VARIANT[currentUser.status]} className="ml-auto">
          {currentUser.status.replace('_', ' ')}
        </Badge>
      </Card>

      {patientProfile && (
        <Card className="mt-4">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-ink-400">IDNP</dt>
              <dd className="text-sm font-medium text-ink-900">
                {patientProfile.idnp}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-400">Date of birth</dt>
              <dd className="text-sm font-medium text-ink-900">
                {formatDate(patientProfile.birth_date)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-400">Weight</dt>
              <dd className="text-sm font-medium text-ink-900">
                {patientProfile.weight_kg} kg
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-400">Height</dt>
              <dd className="text-sm font-medium text-ink-900">
                {patientProfile.height_cm} cm
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-400">Member since</dt>
              <dd className="text-sm font-medium text-ink-900">
                {formatDate(currentUser.created_at)}
              </dd>
            </div>
          </dl>
        </Card>
      )}
    </div>
  );
}

export default Profile;
