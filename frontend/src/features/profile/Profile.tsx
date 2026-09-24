import { useDatasetStore } from '../../store/datasetStore.ts';
import { Card } from '../../components/Card.tsx';
import { Avatar } from '../../components/Avatar.tsx';
import { Badge } from '../../components/Badge.tsx';
import { Skeleton } from '../../components/Skeleton.tsx';
import { formatDate } from '../../utils/formatDate.ts';
import { EmptyState } from '../../components/EmptyState.tsx';
import { Lock } from 'lucide-react';
import { canViewCategory } from '../../lib/recipientAccess.ts';
import type { PatientProfile } from '../../api/types.ts';

const STATUS_VARIANT = {
  active: 'success',
  pending_verification: 'warning',
  locked: 'danger',
  disabled: 'danger',
} as const;

function ProfileDetails({
  profile,
  sinceLabel,
  since,
}: {
  profile: PatientProfile;
  sinceLabel: string;
  since: string;
}) {
  return (
    <Card className="mt-4">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs text-ink-400">IDNP</dt>
          <dd className="text-sm font-medium text-ink-900">{profile.idnp}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">Date of birth</dt>
          <dd className="text-sm font-medium text-ink-900">
            {formatDate(profile.birth_date)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">Weight</dt>
          <dd className="text-sm font-medium text-ink-900">
            {profile.weight_kg} kg
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">Height</dt>
          <dd className="text-sm font-medium text-ink-900">
            {profile.height_cm} cm
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">{sinceLabel}</dt>
          <dd className="text-sm font-medium text-ink-900">
            {formatDate(since)}
          </dd>
        </div>
      </dl>
    </Card>
  );
}

/** Profile page while viewing a recipient's vault, gated by patient_info. */
function RecipientProfile() {
  const recipient = useDatasetStore((state) => state.activeRecipient);
  const profile = useDatasetStore((state) => state.recipientProfile);
  const isLoading = useDatasetStore((state) => state.isLoading);
  if (!recipient) return null;

  if (!canViewCategory(recipient, 'patient_info')) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <EmptyState
          icon={<Lock size={32} />}
          title="Not available"
          description={`${recipient.name} hasn't shared their patient info with you.`}
        />
      </div>
    );
  }

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <Card className="flex items-center gap-4">
        <Avatar name={recipient.name} src={recipient.photoUrl} size="lg" />
        <div>
          <p className="font-sans text-lg font-medium text-ink-900">
            {recipient.name}
          </p>
          <p className="text-sm text-ink-400">{recipient.phone}</p>
        </div>
        <Badge variant="active" className="ml-auto">
          Recipient
        </Badge>
      </Card>

      {isLoading && !profile ? (
        <Card className="mt-4 space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-28" />
        </Card>
      ) : (
        profile && (
          <ProfileDetails
            profile={profile}
            sinceLabel="Caregiver since"
            since={recipient.since}
          />
        )
      )}
    </div>
  );
}

function Profile() {
  const currentUser = useDatasetStore((state) => state.currentUser);
  const patientProfile = useDatasetStore((state) => state.patientProfile);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const isViewingRecipient = useDatasetStore(
    (state) => state.activeRecipient !== null
  );

  if (isViewingRecipient) return <RecipientProfile />;

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
        <ProfileDetails
          profile={patientProfile}
          sinceLabel="Member since"
          since={currentUser.created_at}
        />
      )}
    </div>
  );
}

export default Profile;
