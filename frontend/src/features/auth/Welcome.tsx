import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button.tsx';
import { AuthLayout } from './AuthLayout.tsx';

/** First screen for a browser without a session: choose sign-in or sign-up. */
function Welcome() {
  const navigate = useNavigate();
  const { t } = useTranslation('auth');
  return (
    <AuthLayout subtitle={t('welcome.subtitle')}>
      <div className="space-y-3">
        <Button className="w-full" onClick={() => navigate('/login')}>
          {t('signIn')}
        </Button>
        <Button
          variant="outline"
          className="w-full"
          onClick={() => navigate('/signup')}
        >
          {t('createAccount')}
        </Button>
      </div>
    </AuthLayout>
  );
}

export default Welcome;
