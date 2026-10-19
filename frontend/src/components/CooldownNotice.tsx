import { useTranslation } from 'react-i18next';
import { formatWait } from '../hooks/useCooldown';
import { cn } from '../lib/cn';

interface CooldownNoticeProps {
  /** Seconds left; nothing renders at 0. */
  seconds: number;
  className?: string;
}

/** "Too many attempts. Try again in 14:32." while a rate-limit cooldown runs. */
export function CooldownNotice({ seconds, className }: CooldownNoticeProps) {
  const { t } = useTranslation('common');
  if (seconds <= 0) return null;
  return (
    <p className={cn('text-sm text-coral-500', className)}>
      {/* Announced once; the ticking clock is not a live region, so screen
          readers aren't flooded with a new number every second. */}
      <span role="alert">{t('cooldown.tooMany')}</span>{' '}
      <span role="timer" aria-live="off">
        {t('cooldown.tryAgainIn', { time: formatWait(seconds) })}
      </span>
    </p>
  );
}
