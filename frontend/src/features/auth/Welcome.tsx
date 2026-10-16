import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button.tsx';
import { AuthLayout } from './AuthLayout.tsx';

/** First screen for a browser without a session: choose sign-in or sign-up. */
function Welcome() {
  const navigate = useNavigate();
  return (
    <AuthLayout subtitle="Your medical records from every institution, in one place.">
      <div className="space-y-3">
        <Button className="w-full" onClick={() => navigate('/login')}>
          Sign in
        </Button>
        <Button
          variant="outline"
          className="w-full"
          onClick={() => navigate('/signup')}
        >
          Create account
        </Button>
      </div>
    </AuthLayout>
  );
}

export default Welcome;
