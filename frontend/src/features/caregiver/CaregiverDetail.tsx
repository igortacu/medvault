import { useEffect, useMemo, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDatasetStore } from '../../store/datasetStore';
import { useCaregiverStore } from '../../store/caregiverStore';
import { AddCaregiverModal } from './AddCaregiverModal';
import { Card } from '../../components/Card';
import { Avatar } from '../../components/Avatar';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { Checkbox } from '../../components/CheckBox';
import { Skeleton } from '../../components/Skeleton';
import { EmptyState } from '../../components/EmptyState';
import { useToast } from '../../components/Toast';
import type { CaregiverLinkStatus } from '../../api/caregiver.types';
import type { DataCategory } from '../../api/types';
import { categoryLabel } from './categoryLabels';

const STATUS_VARIANT: Record<
  CaregiverLinkStatus,
  'success' | 'warning' | 'danger'
> = {
  active: 'success',
  pending: 'warning',
  rejected: 'danger',
  revoked: 'danger',
};

function CaregiverDetail() {
  const { t } = useTranslation(['caregiver', 'common']);
  const currentUser = useDatasetStore((state) => state.currentUser);
  const usersWithAccess = useCaregiverStore((state) => state.usersWithAccess);
  const isLoading = useCaregiverStore((state) => state.isLoading);
  const loadUsersWithAccess = useCaregiverStore(
    (state) => state.loadUsersWithAccess
  );
  const updateCaregiverPermissions = useCaregiverStore(
    (state) => state.updateCaregiverPermissions
  );
  const { showToast } = useToast();

  useEffect(() => {
    if (currentUser) loadUsersWithAccess(currentUser.id);
  }, [currentUser, loadUsersWithAccess]);

  const caregiver = usersWithAccess.find((c) => c.status !== 'revoked');

  const initialGranted = useMemo(() => {
    const map = {} as Record<DataCategory, boolean>;
    caregiver?.permissions.forEach((permission) => {
      map[permission.category] = permission.granted;
    });
    return map;
  }, [caregiver]);

  const [granted, setGranted] = useState<Record<DataCategory, boolean>>(
    initialGranted
  );
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setGranted(initialGranted);
  }, [initialGranted]);

  const isDirty = caregiver?.permissions.some(
    (permission) => granted[permission.category] !== permission.granted
  );

  function toggleCategory(category: DataCategory) {
    setGranted((prev) => ({ ...prev, [category]: !prev[category] }));
  }

  async function handleSave() {
    if (!caregiver) return;
    setIsSaving(true);
    try {
      await updateCaregiverPermissions({
        linkId: caregiver.linkId,
        permissions: (Object.keys(granted) as DataCategory[]).filter(
          (category) => granted[category]
        ),
      });
      showToast({
        variant: 'success',
        title: t('detail.saved'),
        description: t('detail.savedDescription', { name: caregiver.name }),
      });
    } catch {
      showToast({
        variant: 'error',
        title: t('detail.saveFailed'),
        description: t('common:pleaseTryAgain'),
      });
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading && usersWithAccess.length === 0) {
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

  if (!caregiver) {
    return (
      <div className="px-4 py-6 sm:px-6 lg:px-10">
        <h1 className="font-display text-xl font-semibold text-ink-900">
          {t('detail.title')}
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          {t('detail.subtitle')}
        </p>

        <div className="mt-6">
          <EmptyState
            icon={<ShieldCheck size={32} />}
            title={t('detail.emptyTitle')}
            description={t('detail.emptyDescription')}
            action={
              currentUser && <AddCaregiverModal patientId={currentUser.id} />
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <h1 className="font-display text-xl font-semibold text-ink-900">
        {t('detail.title')}
      </h1>
      <p className="mt-1 text-sm text-ink-400">
        {t('detail.subtitle')}
      </p>

      <Card className="mt-6 flex items-center gap-4">
        <Avatar name={caregiver.name} size="lg" />
        <div>
          <p className="font-sans text-lg font-medium text-ink-900">
            {caregiver.name}
          </p>
          <p className="text-sm text-ink-400">{caregiver.phone}</p>
        </div>
        <Badge variant={STATUS_VARIANT[caregiver.status]} className="ml-auto">
          {t(`detail.status.${caregiver.status}`)}
        </Badge>
      </Card>

      <Card className="mt-4">
        <p className="font-display text-base font-semibold text-ink-900">
          {t('detail.permissions')}
        </p>
        <p className="mt-1 text-sm text-ink-400">
          {t('detail.permissionsHint', { name: caregiver.name })}
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {caregiver.permissions.map((permission) => (
            <Checkbox
              key={permission.category}
              id={`permission-${permission.category}`}
              label={categoryLabel(permission.category)}
              checked={granted[permission.category] ?? false}
              onChange={() => toggleCategory(permission.category)}
            />
          ))}
        </div>

        <div className="mt-6 flex justify-end">
          <Button
            variant="primary"
            disabled={!isDirty}
            isLoading={isSaving}
            onClick={handleSave}
          >
            {t('detail.save')}
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default CaregiverDetail;
