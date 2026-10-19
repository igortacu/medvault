import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { authApi, type Challenge } from '../../api/authService.ts';
import { isUnauthorized } from '../../api/errors.ts';
import { Button } from '../../components/Button.tsx';
import { CooldownNotice } from '../../components/CooldownNotice.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { Input } from '../../components/Input.tsx';
import { useCooldown } from '../../hooks/useCooldown.ts';
import { useDatasetStore } from '../../store/datasetStore.ts';
import { AuthLayout } from './AuthLayout.tsx';
import { CodeStep } from './CodeStep.tsx';

function Login() {
  const navigate = useNavigate();
  const { t } = useTranslation('auth');
  const [phone, setPhone] = useState('+373');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const cooldown = useCooldown();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      setChallenge(await authApi.login(phone.trim(), password));
    } catch (err) {
      if (!cooldown.trigger(err)) {
        setError(isUnauthorized(err) ? t('login.invalid') : t('login.failed'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (challenge) {
    return (
      <AuthLayout subtitle={t('login.confirmSubtitle')}>
        <CodeStep
          phone={phone.trim()}
          challenge={challenge}
          onChallenge={setChallenge}
          onRestart={() => {
            setChallenge(null);
            setPassword('');
          }}
          onVerify={async (code) => {
            await authApi.verifyLogin(challenge.challengeId, code);
            // The redirect that brought us here set this; sign-in is what clears it.
            useDatasetStore.setState({ needsLogin: false });
            navigate('/profile', { replace: true });
          }}
        />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout subtitle={t('login.subtitle')}>
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <FormField label={t('field.phone')} required>
          <Input
            type="tel"
            name="phone"
            autoComplete="tel"
            inputMode="tel"
            placeholder="+37369000000"
            leftIcon={<Phone size={16} />}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
          />
        </FormField>

        <FormField label={t('field.password')} required>
          <Input
            type="password"
            name="password"
            autoComplete="current-password"
            leftIcon={<Lock size={16} />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
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
          isLoading={isSubmitting}
          disabled={!phone.trim() || !password || cooldown.active}
        >
          {t('continue')}
        </Button>

        <div className="flex justify-between text-sm">
          <Link
            to="/forgot-password"
            className="text-primary-600 hover:underline"
          >
            {t('login.forgotPassword')}
          </Link>
          <Link to="/signup" className="text-primary-600 hover:underline">
            {t('createAccount')}
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}

export default Login;
