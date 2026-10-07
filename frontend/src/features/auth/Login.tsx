import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, Phone } from 'lucide-react';
import { datasetApi } from '../../api';
import { isUnauthorized } from '../../api/errors.ts';
import { Button } from '../../components/Button.tsx';
import { Card } from '../../components/Card.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { Input } from '../../components/Input.tsx';

function Login() {
  const navigate = useNavigate();
  const [phone, setPhone] = useState('+373');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await datasetApi.login(phone.trim(), password);
      navigate('/profile', { replace: true });
    } catch (err) {
      setError(
        isUnauthorized(err)
          ? 'Invalid phone or password.'
          : "Couldn't sign in. Please try again."
      );
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-primary-50/40 px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="text-center font-display text-2xl font-semibold tracking-tight text-primary-600">
          Medvault
        </h1>
        <p className="mt-2 text-center text-sm text-ink-600">
          Sign in to your medical vault.
        </p>

        <Card className="mt-8 p-6">
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <FormField label="Phone number" required>
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

            <FormField label="Password" required>
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

            <Button
              type="submit"
              className="w-full"
              isLoading={isSubmitting}
              disabled={!phone.trim() || !password}
            >
              Sign in
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}

export default Login;
