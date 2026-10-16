import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Phone } from 'lucide-react';
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
import { PasswordInput } from './PasswordInput.tsx';
import { PasswordStrength } from './PasswordStrength.tsx';
import { passwordChecks } from './passwordRules.ts';
import {
  isoDate,
  normalizePhone,
  validateConfirm,
  validateDob,
  validateName,
  validatePhone,
} from './signupRules.ts';

// In form order, so a failed submit can focus the first invalid field.
const FIELDS = [
  'first_name',
  'last_name',
  'phone',
  'date_of_birth',
  'password',
  'confirm_password',
] as const;
type FieldName = (typeof FIELDS)[number];
type Form = Record<FieldName, string>;

function validate(form: Form): Partial<Record<FieldName, string>> {
  const errors: Partial<Record<FieldName, string | null>> = {
    first_name: validateName(form.first_name),
    last_name: validateName(form.last_name),
    phone: validatePhone(form.phone),
    date_of_birth: validateDob(form.date_of_birth),
    password: passwordChecks(form.password).every((c) => c.ok)
      ? null
      : 'Password doesn’t meet all the requirements below.',
    confirm_password: validateConfirm(form.password, form.confirm_password),
  };
  return Object.fromEntries(
    Object.entries(errors).filter(([, message]) => message)
  ) as Partial<Record<FieldName, string>>;
}

function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState<Form>({
    first_name: '',
    last_name: '',
    phone: '+373',
    date_of_birth: '',
    password: '',
    confirm_password: '',
  });
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>(
    {}
  );
  const [submitted, setSubmitted] = useState(false);
  const [serverErrors, setServerErrors] = useState<
    Partial<Record<FieldName, string>>
  >({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [challenge, setChallenge] = useState<Challenge | null>(null);

  const clientErrors = validate(form);
  // A backend message wins until the user edits that field; client checks show
  // once a field has been left or a submit was attempted.
  const errorFor = (name: FieldName) =>
    serverErrors[name] ??
    (touched[name] || submitted ? clientErrors[name] : undefined);

  const bind = (name: FieldName) => ({
    name,
    value: form[name],
    onChange: (e: { target: { value: string } }) => {
      setForm((f) => ({ ...f, [name]: e.target.value }));
      setServerErrors((e) => ({ ...e, [name]: undefined }));
    },
    onBlur: () => setTouched((t) => ({ ...t, [name]: true })),
  });

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    setFormError(null);

    const firstInvalid = FIELDS.find((f) => clientErrors[f]);
    if (firstInvalid) {
      event.currentTarget
        .querySelector<HTMLInputElement>(`[name="${firstInvalid}"]`)
        ?.focus();
      return;
    }

    setIsSubmitting(true);
    try {
      setChallenge(
        await authApi.signup({
          firstName: form.first_name.trim(),
          lastName: form.last_name.trim(),
          phone: normalizePhone(form.phone)!,
          dateOfBirth: form.date_of_birth,
          password: form.password,
        })
      );
    } catch (err) {
      if (err instanceof FieldErrors) {
        setServerErrors(err.errors as Partial<Record<FieldName, string>>);
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
    const phone = normalizePhone(form.phone) ?? form.phone.trim();
    return (
      <AuthLayout subtitle="Verify your phone number.">
        <CodeStep
          phone={phone}
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

  return (
    <AuthLayout subtitle="Create your medical vault.">
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-3">
          <FormField label="First name" error={errorFor('first_name')} required>
            <Input autoComplete="given-name" {...bind('first_name')} />
          </FormField>
          <FormField label="Surname" error={errorFor('last_name')} required>
            <Input autoComplete="family-name" {...bind('last_name')} />
          </FormField>
        </div>

        <FormField
          label="Phone number"
          error={errorFor('phone')}
          hint="We'll text you a verification code."
          required
        >
          <Input
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            placeholder="+37369000000"
            leftIcon={<Phone size={16} />}
            {...bind('phone')}
          />
        </FormField>

        <FormField
          label="Date of birth"
          error={errorFor('date_of_birth')}
          required
        >
          <Input
            type="date"
            autoComplete="bday"
            max={isoDate(new Date())}
            {...bind('date_of_birth')}
          />
        </FormField>

        <div className="space-y-2">
          <FormField label="Password" error={errorFor('password')} required>
            <PasswordInput autoComplete="new-password" {...bind('password')} />
          </FormField>
          <PasswordStrength password={form.password} />
        </div>

        <FormField
          label="Confirm password"
          error={errorFor('confirm_password')}
          required
        >
          <PasswordInput
            autoComplete="new-password"
            {...bind('confirm_password')}
          />
        </FormField>

        {formError && (
          <p role="alert" className="text-sm text-coral-500">
            {formError}
          </p>
        )}

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
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
