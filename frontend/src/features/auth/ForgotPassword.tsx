import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  authApi,
  FieldErrors,
  RateLimited,
  type Challenge,
} from '../../api/authService.ts';
import { Button } from '../../components/Button.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { Input } from '../../components/Input.tsx';
import { AuthLayout } from './AuthLayout.tsx';
import { CodeStep } from './CodeStep.tsx';
import { PasswordStrength } from './PasswordStrength.tsx';
import { passwordChecks } from './passwordRules.ts';

type Step =
  | { name: 'phone' }
  | { name: 'code'; challenge: Challenge }
  | { name: 'password'; resetToken: string }
  | { name: 'done' };

function ForgotPassword() {
  const navigate = useNavigate();
  const { t } = useTranslation('auth');
  const [step, setStep] = useState<Step>({ name: 'phone' });
  const [phone, setPhone] = useState('+373');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const requestCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const challenge = await authApi.requestPasswordReset(phone.trim());
      setStep({ name: 'code', challenge });
    } catch (err) {
      setError(
        err instanceof RateLimited
          ? t('error.tooManyAttempts')
          : t('reset.startFailed')
      );
    } finally {
      setBusy(false);
    }
  };

  const setNewPassword = async (event: FormEvent) => {
    event.preventDefault();
    if (step.name !== 'password') return;
    setError(null);
    setBusy(true);
    try {
      await authApi.confirmPasswordReset(step.resetToken, password);
      setStep({ name: 'done' });
    } catch (err) {
      if (err instanceof FieldErrors) {
        setError(err.errors.new_password ?? t('reset.notAllowed'));
      } else {
        setError(t('reset.expired'));
        setStep({ name: 'phone' });
      }
    } finally {
      setBusy(false);
    }
  };

  if (step.name === 'code') {
    return (
      <AuthLayout subtitle={t('reset.subtitle')}>
        <CodeStep
          phone={phone.trim()}
          challenge={step.challenge}
          onChallenge={(challenge) => setStep({ name: 'code', challenge })}
          onRestart={() => setStep({ name: 'phone' })}
          onVerify={async (code) => {
            const resetToken = await authApi.verifyPasswordReset(
              step.challenge.challengeId,
              code
            );
            setStep({ name: 'password', resetToken });
          }}
        />
      </AuthLayout>
    );
  }

  if (step.name === 'password') {
    return (
      <AuthLayout subtitle={t('reset.chooseSubtitle')}>
        <form onSubmit={setNewPassword} noValidate className="space-y-5">
          <FormField label={t('field.newPassword')} required>
            <Input
              type="password"
              autoComplete="new-password"
              leftIcon={<Lock size={16} />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </FormField>
          <PasswordStrength password={password} />
          {error && (
            <p role="alert" className="text-sm text-coral-500">
              {error}
            </p>
          )}
          <Button
            type="submit"
            className="w-full"
            isLoading={busy}
            disabled={!passwordChecks(password).every((c) => c.ok)}
          >
            {t('reset.setPassword')}
          </Button>
        </form>
      </AuthLayout>
    );
  }

  if (step.name === 'done') {
    return (
      <AuthLayout subtitle={t('reset.doneSubtitle')}>
        <p className="text-sm text-ink-600">{t('reset.doneText')}</p>
        <Button className="mt-5 w-full" onClick={() => navigate('/login')}>
          {t('reset.goToSignIn')}
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout subtitle={t('reset.subtitle')}>
      <form onSubmit={requestCode} noValidate className="space-y-5">
        <FormField
          label={t('field.phone')}
          hint={t('reset.phoneHint')}
          required
        >
          <Input
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            placeholder="+37369000000"
            leftIcon={<Phone size={16} />}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </FormField>
        {error && (
          <p role="alert" className="text-sm text-coral-500">
            {error}
          </p>
        )}
        <Button
          type="submit"
          className="w-full"
          isLoading={busy}
          disabled={phone.trim().length <= 4}
        >
          {t('reset.sendCode')}
        </Button>
        <p className="text-center text-sm">
          <Link to="/login" className="text-primary-600 hover:underline">
            {t('reset.backToSignIn')}
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export default ForgotPassword;
