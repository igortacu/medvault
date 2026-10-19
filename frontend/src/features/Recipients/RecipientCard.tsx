import { ArrowLeftRight, UserX } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card } from '../../components/Card';
import { Avatar } from '../../components/Avatar';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { categoryLabel } from '../caregiver/categoryLabels';
import { formatDate } from '../../utils/formatDate';
import { cn } from '../../lib/cn';
import type { CareRecipient } from '../../api/caregiver.types';

export interface RecipientCardProps {
  recipient: CareRecipient;
  onReject: (recipient: CareRecipient) => void;
  onSwitch: (recipient: CareRecipient) => void;
  onSwitchBack: () => void;
  /** This recipient's vault is the one currently open. */
  isActive: boolean;
}

function getAge(birthDate: string) {
  const birth = new Date(birthDate);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const hadBirthday =
    today.getMonth() > birth.getMonth() ||
    (today.getMonth() === birth.getMonth() &&
      today.getDate() >= birth.getDate());
  if (!hadBirthday) age -= 1;
  return age;
}

/**
 * A single person the current user cares for: who they are, which categories
 * they've shared, and the caregiver-side actions (switch into their vault,
 * stop being their caregiver).
 */
export function RecipientCard({
  recipient,
  onReject,
  onSwitch,
  onSwitchBack,
  isActive,
}: RecipientCardProps) {
  const { t } = useTranslation('caregiver');
  const grantedPermissions = recipient.permissions.filter((p) => p.granted);
  const details = [
    recipient.birthDate &&
      t('card.age', { count: getAge(recipient.birthDate) }),
    recipient.phone,
    t('card.since', { date: formatDate(recipient.since) }),
  ].filter(Boolean);

  return (
    <Card
      className={cn(
        'flex flex-col gap-4',
        isActive && 'ring-2 ring-primary-500'
      )}
      aria-current={isActive || undefined}
    >
      <div className="flex items-start gap-4">
        <Avatar name={recipient.name} src={recipient.photoUrl} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-sans text-base font-medium text-ink-900">
            {recipient.name}
          </p>
          <p className="text-sm text-ink-400">{details.join(' · ')}</p>
        </div>
        {isActive && <Badge variant="active">{t('card.active')}</Badge>}
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-ink-400">
          {t('card.sharedWithYou')}
        </p>
        {grantedPermissions.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {grantedPermissions.map((permission) => (
              <Badge key={permission.category} variant="neutral">
                {categoryLabel(permission.category)}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-ink-400">{t('noCategoriesShared')}</p>
        )}
      </div>

      <div className="flex justify-end gap-3">
        {isActive ? (
          <Button variant="primary" size="sm" onClick={onSwitchBack}>
            <ArrowLeftRight size={16} aria-hidden="true" />
            {t('card.switchBack')}
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSwitch(recipient)}
          >
            <ArrowLeftRight size={16} aria-hidden="true" />
            {t('card.switch')}
          </Button>
        )}
        <Button variant="danger" size="sm" onClick={() => onReject(recipient)}>
          <UserX size={16} aria-hidden="true" />
          {t('card.reject')}
        </Button>
      </div>
    </Card>
  );
}
