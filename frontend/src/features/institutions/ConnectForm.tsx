import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/Button';
import { Checkbox } from '../../components/CheckBox';
import { FormField } from '../../components/Formfield';
import { Input } from '../../components/Input';
import type { Institution } from '../../api/types';
import { CONSENT_POINTS } from './consent';
import { normalizeIdnp, validateIdnp } from './connectionRules';

export interface ConnectFormProps {
  /** The institutions this consent covers, listed for the patient to read. */
  institutions: Institution[];
  /** Let the patient untick institutions; all start ticked. */
  selectable?: boolean;
  submitLabel: string;
  isSubmitting?: boolean;
  /** Shown above the institution list, e.g. a picker for "Add institution". */
  children?: ReactNode;
  /** Extra buttons next to submit (e.g. Cancel in a modal). */
  secondaryAction?: ReactNode;
  /** Receives the IDNP and the institutions the consent was given for. */
  onSubmit: (idnp: string, institutionIds: string[]) => void;
}

/**
 * IDNP + one consent screen. The IDNP lives only in this component's state
 * and is handed straight to onSubmit; it is never written anywhere else.
 */
export function ConnectForm({
  institutions,
  selectable,
  submitLabel,
  isSubmitting,
  children,
  secondaryAction,
  onSubmit,
}: ConnectFormProps) {
  const { t } = useTranslation('institutions');
  const consentId = useId();
  const listId = useId();
  const [idnp, setIdnp] = useState('');
  const [idnpError, setIdnpError] = useState<string | null>(null);
  const [consented, setConsented] = useState(false);
  const [consentError, setConsentError] = useState(false);
  // Track the unticked ones, so an institution that appears later starts
  // ticked like the rest.
  const [unticked, setUnticked] = useState<Set<string>>(() => new Set());
  const [selectionError, setSelectionError] = useState(false);

  const chosen = selectable
    ? institutions.filter((i) => !unticked.has(i.id))
    : institutions;
  const allChosen = chosen.length === institutions.length;

  function toggle(institutionId: string) {
    setSelectionError(false);
    setUnticked((previous) => {
      const next = new Set(previous);
      if (next.has(institutionId)) next.delete(institutionId);
      else next.add(institutionId);
      return next;
    });
  }

  function toggleAll() {
    setSelectionError(false);
    setUnticked(allChosen ? new Set(institutions.map((i) => i.id)) : new Set());
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const error = validateIdnp(idnp);
    setIdnpError(error);
    setConsentError(!consented);
    setSelectionError(institutions.length > 0 && chosen.length === 0);
    if (error || !consented || chosen.length === 0) return;
    onSubmit(
      normalizeIdnp(idnp),
      chosen.map((i) => i.id)
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <FormField
        label={t('form.idnp')}
        required
        error={idnpError ?? undefined}
        hint={t('form.idnpHint')}
      >
        <Input
          inputMode="numeric"
          autoComplete="off"
          maxLength={16}
          placeholder="2001234567890"
          value={idnp}
          onChange={(e) => {
            setIdnp(e.target.value);
            if (idnpError) setIdnpError(null);
          }}
        />
      </FormField>

      {children}

      {institutions.length > 0 && (
        <div className="rounded-xl border border-ink-400/20 bg-primary-50/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 font-sans text-sm font-medium text-ink-900">
              <ShieldCheck size={16} className="text-primary-600" aria-hidden />
              {chosen.length === 0
                ? t('form.choose')
                : chosen.length === 1
                  ? t('form.connectingToOne', { name: chosen[0].name })
                  : t('form.connectingTo', { count: chosen.length })}
            </p>
            {selectable && institutions.length > 1 && (
              <button
                type="button"
                onClick={toggleAll}
                className="rounded-md text-sm font-medium text-primary-600 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
              >
                {allChosen ? t('form.clearAll') : t('form.selectAll')}
              </button>
            )}
          </div>

          {selectable ? (
            <fieldset className="mt-3">
              <legend className="sr-only">{t('form.listLegend')}</legend>
              <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                {institutions.map((institution) => (
                  <Checkbox
                    key={institution.id}
                    id={`${listId}-${institution.id}`}
                    checked={!unticked.has(institution.id)}
                    onChange={() => toggle(institution.id)}
                    label={
                      institution.city
                        ? `${institution.name} · ${institution.city}`
                        : institution.name
                    }
                  />
                ))}
              </div>
              {selectionError && (
                <p className="mt-2 text-sm text-coral-500">
                  {t('form.chooseOne')}
                </p>
              )}
            </fieldset>
          ) : (
            institutions.length > 1 && (
              <ul className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 text-sm text-ink-600 sm:grid-cols-2">
                {institutions.map((institution) => (
                  <li key={institution.id}>
                    {institution.name}
                    {institution.city && (
                      <span className="text-ink-400">
                        {' '}
                        · {institution.city}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )
          )}

          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-600">
            {CONSENT_POINTS.map((point) => (
              <li key={point}>{t(`consent.${point}`)}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <Checkbox
          id={consentId}
          invalid={consentError}
          checked={consented}
          onChange={(e) => {
            setConsented(e.target.checked);
            if (e.target.checked) setConsentError(false);
          }}
          label={chosen.length === 1 ? t('form.agreeOne') : t('form.agreeMany')}
        />
        {consentError && (
          <p className="mt-1 text-sm text-coral-500">
            {t('form.consentRequired')}
          </p>
        )}
      </div>

      <div className="flex flex-wrap justify-end gap-3">
        {secondaryAction}
        <Button
          type="submit"
          isLoading={isSubmitting}
          disabled={institutions.length === 0}
        >
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
