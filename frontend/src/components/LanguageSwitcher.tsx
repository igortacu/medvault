import { useTranslation } from 'react-i18next';
import { setLanguage } from '../i18n';
import { LANGUAGES } from '../i18n/languages';
import { cn } from '../lib/cn';

export interface LanguageSwitcherProps {
  /** "dark" sits on the primary-coloured sidebar, "light" on white pages. */
  tone?: 'light' | 'dark';
  className?: string;
}

/** RO / EN / RU toggle; the choice is remembered for the next visit. */
export function LanguageSwitcher({
  tone = 'light',
  className,
}: LanguageSwitcherProps) {
  const { t, i18n } = useTranslation();
  const current = i18n.resolvedLanguage;

  return (
    <div
      role="group"
      aria-label={t('language')}
      className={cn(
        'inline-flex rounded-pill border p-0.5',
        tone === 'dark' ? 'border-white/20' : 'border-ink-400/25 bg-white',
        className
      )}
    >
      {LANGUAGES.map((language) => {
        const active = language.code === current;
        return (
          <button
            key={language.code}
            type="button"
            lang={language.code}
            title={language.name}
            aria-pressed={active}
            onClick={() => void setLanguage(language.code)}
            className={cn(
              'rounded-pill px-2.5 py-1 text-xs font-semibold tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2',
              tone === 'dark'
                ? active
                  ? 'bg-white text-primary-600 focus-visible:ring-white'
                  : 'text-primary-50 hover:bg-white/10 focus-visible:ring-white'
                : active
                  ? 'bg-primary-600 text-white focus-visible:ring-primary-500'
                  : 'text-ink-600 hover:bg-primary-50 focus-visible:ring-primary-500'
            )}
          >
            <span aria-hidden="true">{language.short}</span>
            <span className="sr-only">{language.name}</span>
          </button>
        );
      })}
    </div>
  );
}
