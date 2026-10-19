import { useTranslation } from 'react-i18next';
import { passwordChecks } from './passwordRules.ts';

export function PasswordStrength({ password }: { password: string }) {
  const { t } = useTranslation('auth');
  const checks = passwordChecks(password);
  const met = checks.filter((c) => c.ok).length;
  return (
    <div>
      <div className="flex gap-1" aria-hidden="true">
        {checks.map((_, i) => (
          <span
            key={i}
            className={`h-1 flex-1 rounded-full ${
              i < met
                ? met === checks.length
                  ? 'bg-primary-500'
                  : 'bg-coral-500'
                : 'bg-ink-400/20'
            }`}
          />
        ))}
      </div>
      <ul className="mt-2 grid grid-cols-1 gap-0.5 text-xs">
        {checks.map((c) => (
          <li key={c.rule} className={c.ok ? 'text-primary-600' : 'text-ink-600'}>
            {c.ok ? '✓' : '•'} {t(`passwordRule.${c.rule}`)}
          </li>
        ))}
      </ul>
    </div>
  );
}
