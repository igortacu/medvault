import { useEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { ApiError } from '../../api/errors.ts';
import { RateLimited, type Challenge, authApi } from '../../api/authService.ts';
import { Button } from '../../components/Button.tsx';
import { CooldownNotice } from '../../components/CooldownNotice.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { OTPInput } from '../../components/OTPInput.tsx';
import { useCooldown } from '../../hooks/useCooldown.ts';

const RESEND_COOLDOWN_SECONDS = 30;
// Lets the "start again" message be read before the flow resets.
const RESTART_DELAY_MS = 1500;

const formatClock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

/** Counts down from `from` seconds; the setter restarts it. */
function useCountdown(from: number) {
  const [left, setLeft] = useState(from);
  useEffect(() => {
    if (left <= 0) return;
    const t = window.setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => window.clearTimeout(t);
  }, [left]);
  return [left, setLeft] as const;
}

interface CodeStepProps {
  phone: string;
  challenge: Challenge;
  onChallenge: (next: Challenge) => void;
  /** Resolves on success; throws to show an error. */
  onVerify: (code: string) => Promise<void>;
  /** Called when the challenge can no longer be completed (expired or capped). */
  onRestart: () => void;
}

/** SMS code entry: 5-minute expiry countdown, capped resend with cooldown. */
export function CodeStep({
  phone,
  challenge,
  onChallenge,
  onVerify,
  onRestart,
}: CodeStepProps) {
  const { t } = useTranslation('auth');
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expiresLeft, setExpiresLeft] = useCountdown(challenge.expiresIn);
  const [cooldown, setCooldown] = useCountdown(RESEND_COOLDOWN_SECONDS);
  // Too many code entries from this phone and IP: the backend's cooldown.
  const limited = useCooldown();
  const expired = expiresLeft <= 0;

  // State is read through refs where an async handler could otherwise see a stale
  // value: a completed OTP fires onComplete and the Verify button can fire right after.
  const submitting = useRef(false);
  const restartTimer = useRef<number | undefined>(undefined);
  const container = useRef<HTMLDivElement>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      window.clearTimeout(restartTimer.current);
    };
  }, []);

  const restartSoon = () => {
    window.clearTimeout(restartTimer.current);
    restartTimer.current = window.setTimeout(() => {
      if (mounted.current) onRestart();
    }, RESTART_DELAY_MS);
  };

  const focusFirstBox = () =>
    window.setTimeout(
      () => container.current?.querySelector('input')?.focus(),
      0
    );

  const submit = async (value: string) => {
    if (submitting.current || expired || value.length !== 6) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      await onVerify(value);
    } catch (err) {
      if (!mounted.current) return;
      if (err instanceof RateLimited && err.retryAfter !== null) {
        limited.start(err.retryAfter);
      } else if (err instanceof RateLimited) {
        setError(t('code.tooManyWrong'));
        restartSoon();
      } else if (err instanceof ApiError && err.status === 400) {
        setError(t('code.incorrect'));
        focusFirstBox();
      } else if (err instanceof ApiError && err.status === 401) {
        setError(t('code.noLongerValid'));
        restartSoon();
      } else {
        // Network trouble or a server error: the code may well be fine.
        setError(t('code.somethingWrong'));
        focusFirstBox();
      }
      setCode('');
    } finally {
      submitting.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  const resend = async () => {
    setError(null);
    try {
      const next = await authApi.resendCode(challenge.challengeId);
      onChallenge(next);
      setExpiresLeft(next.expiresIn);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      setCode('');
      focusFirstBox();
    } catch (err) {
      if (err instanceof RateLimited && err.retryAfter === null) {
        setError(t('code.resendLimit'));
        restartSoon();
      } else if (err instanceof RateLimited) {
        setCooldown(err.retryAfter ?? RESEND_COOLDOWN_SECONDS);
      } else if (err instanceof ApiError && err.status === 400) {
        setError(t('code.expiredStartAgain'));
      } else {
        setError(t('code.resendFailed'));
      }
    }
  };

  return (
    <div className="space-y-5" ref={container}>
      <p className="text-sm text-ink-600">
        <Trans
          t={t}
          i18nKey="code.sentTo"
          values={{ phone }}
          components={{ bold: <span className="font-medium" /> }}
        />
      </p>

      <FormField label={t('code.label')} error={error ?? undefined}>
        <OTPInput
          value={code}
          onChange={setCode}
          onComplete={submit}
          disabled={busy || expired || limited.active}
        />
      </FormField>
      <CooldownNotice seconds={limited.secondsLeft} />

      {/* Not a live region: a per-second update would flood screen readers. */}
      <p className="text-sm text-ink-600" role="timer" aria-live="off">
        {expired
          ? t('code.expired')
          : t('code.expiresIn', { time: formatClock(expiresLeft) })}
      </p>
      {expired && (
        <p role="status" className="sr-only">
          {t('code.expired')}
        </p>
      )}

      <Button
        className="w-full"
        isLoading={busy}
        disabled={code.length !== 6 || expired || limited.active}
        onClick={() => submit(code)}
      >
        {t('code.verify')}
      </Button>

      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          // An expired code can no longer be resent (the server dropped it).
          disabled={expired || cooldown > 0}
          onClick={resend}
        >
          {cooldown > 0 && !expired
            ? cooldown < 60
              ? t('code.resendIn', { seconds: cooldown })
              : t('code.resendInTime', { time: formatClock(cooldown) })
            : t('code.resend')}
        </Button>
        <Button
          variant={expired ? 'primary' : 'ghost'}
          size="sm"
          onClick={onRestart}
        >
          {t('code.startOver')}
        </Button>
      </div>
    </div>
  );
}
