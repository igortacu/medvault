import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Phone } from 'lucide-react';
import {
  authApi,
  FieldErrors,
  RateLimited,
  type Challenge,
} from '../../api/authService.ts';
import { ApiError } from '../../api/errors.ts';
import { Button } from '../../components/Button.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { Input } from '../../components/Input.tsx';
import { useDatasetStore } from '../../store/datasetStore.ts';
import { AuthLayout } from './AuthLayout.tsx';
import { CodeStep } from './CodeStep.tsx';
import { PasswordStrength } from './PasswordStrength.tsx';
import { passwordChecks } from './passwordRules.ts';

type FieldName =
  | 'first_name'
  | 'last_name'
  | 'phone'
  | 'date_of_birth'
  | 'password';

function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    phone: '+373',
    dateOfBirth: '',
    password: '',
  });
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [challenge, setChallenge] = useState<Challenge | null>(null);

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors({});
    setFormError(null);
    setIsSubmitting(true);
    try {
      setChallenge(
        await authApi.signup({ ...form, phone: form.phone.trim() })
      );
    } catch (err) {
      if (err instanceof FieldErrors) {
        setErrors(err.errors as Partial<Record<FieldName, string>>);
      } else if (err instanceof RateLimited) {
        setFormError('Too many attempts. Please try again later.');
      } else if (err instanceof ApiError && err.status === 409) {
        setFormError("We couldn't create an account with these details.");
      } else {
        setFormError("Couldn't create the account. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (challenge) {
    return (
      <AuthLayout subtitle="Verify your phone number.">
        <CodeStep
          phone={form.phone.trim()}
          challenge={challenge}
          onChallenge={setChallenge}
          onRestart={() => setChallenge(null)}
          onVerify={async (code) => {
            await authApi.verifySignup(challenge.challengeId, code);
            // The redirect that brought us here set this; sign-in is what clears it.
            useDatasetStore.setState({ needsLogin: false });
            navigate('/profile', { replace: true });
          }}
        />
      </AuthLayout>
    );
  }

  const ready =
    form.firstName.trim() &&
    form.lastName.trim() &&
    form.phone.trim().length > 4 &&
    form.dateOfBirth &&
    passwordChecks(form.password).every((c) => c.ok);

  return (
    <AuthLayout subtitle="Create your medical vault.">
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="First name" error={errors.first_name} required>
            <Input
              name="first_name"
              autoComplete="given-name"
              value={form.firstName}
              onChange={set('firstName')}
            />
          </FormField>
          <FormField label="Surname" error={errors.last_name} required>
            <Input
              name="last_name"
              autoComplete="family-name"
              value={form.lastName}
              onChange={set('lastName')}
            />
          </FormField>
        </div>

        <FormField
          label="Phone number"
          error={errors.phone}
          hint="We'll text you a verification code."
          required
        >
          <Input
            type="tel"
            name="phone"
            autoComplete="tel"
            inputMode="tel"
            placeholder="+37369000000"
            leftIcon={<Phone size={16} />}
            value={form.phone}
            onChange={set('phone')}
          />
        </FormField>

        <FormField label="Date of birth" error={errors.date_of_birth} required>
          <Input
            type="date"
            name="dob"
            autoComplete="bday"
            max={new Date().toISOString().slice(0, 10)}
            value={form.dateOfBirth}
            onChange={set('dateOfBirth')}
          />
        </FormField>

        <div className="space-y-2">
          <FormField label="Password" error={errors.password} required>
            <Input
              type="password"
              name="password"
              autoComplete="new-password"
              leftIcon={<Lock size={16} />}
              value={form.password}
              onChange={set('password')}
            />
          </FormField>
          <PasswordStrength password={form.password} />
        </div>

        {formError && (
          <p role="alert" className="text-sm text-coral-500">
            {formError}
          </p>
        )}

        <Button
          type="submit"
          className="w-full"
          isLoading={isSubmitting}
          disabled={!ready}
        >
          Create account
        </Button>

        <p className="text-center text-sm text-ink-600">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export default Signup;
