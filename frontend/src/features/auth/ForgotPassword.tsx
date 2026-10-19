import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Phone } from 'lucide-react';
import { authApi, FieldErrors, type Challenge } from '../../api/authService.ts';
import { Button } from '../../components/Button.tsx';
import { CooldownNotice } from '../../components/CooldownNotice.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { Input } from '../../components/Input.tsx';
import { useCooldown } from '../../hooks/useCooldown.ts';
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
  const [step, setStep] = useState<Step>({ name: 'phone' });
  const [phone, setPhone] = useState('+373');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cooldown = useCooldown();

  const requestCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const challenge = await authApi.requestPasswordReset(phone.trim());
      setStep({ name: 'code', challenge });
    } catch (err) {
      if (!cooldown.trigger(err)) {
        setError("Couldn't start the reset. Please try again.");
      }
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
        setError(err.errors.new_password ?? 'That password is not allowed.');
      } else {
        setError('This reset has expired. Please start again.');
        setStep({ name: 'phone' });
      }
    } finally {
      setBusy(false);
    }
  };

  if (step.name === 'code') {
    return (
      <AuthLayout subtitle="Reset your password.">
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
      <AuthLayout subtitle="Choose a new password.">
        <form onSubmit={setNewPassword} noValidate className="space-y-5">
          <FormField label="New password" required>
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
            Set password
          </Button>
        </form>
      </AuthLayout>
    );
  }

  if (step.name === 'done') {
    return (
      <AuthLayout subtitle="Password updated.">
        <p className="text-sm text-ink-600">
          Your password was changed and you were signed out everywhere. Sign in
          with the new one.
        </p>
        <Button className="mt-5 w-full" onClick={() => navigate('/login')}>
          Go to sign in
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout subtitle="Reset your password.">
      <form onSubmit={requestCode} noValidate className="space-y-5">
        <FormField
          label="Phone number"
          hint="If the number is registered, we'll text you a code."
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
        <CooldownNotice seconds={cooldown.secondsLeft} />
        <Button
          type="submit"
          className="w-full"
          isLoading={busy}
          disabled={phone.trim().length <= 4 || cooldown.active}
        >
          Send code
        </Button>
        <p className="text-center text-sm">
          <Link to="/login" className="text-primary-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export default ForgotPassword;
