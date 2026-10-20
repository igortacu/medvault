import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type {
  DataCategory,
  DataExport,
  ExportFormat,
  ExportRequest,
} from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Checkbox } from '../../components/CheckBox';
import { CooldownNotice } from '../../components/CooldownNotice';
import { useToast } from '../../components/Toast';
import { useCooldown } from '../../hooks/useCooldown';
import { cn } from '../../lib/cn';
import { ExportItem } from './ExportItem';
import { exportLanguage, isPending, useExports, useNow } from './useExports';

// The order the categories are offered (and appear in the file).
const CATEGORIES: DataCategory[] = [
  'patient_info',
  'diagnoses',
  'certificates',
  'analyses',
  'prescriptions',
  'other_med_info',
];
const FORMATS: ExportFormat[] = ['pdf', 'json'];
const RECENT = 5;

/** "Export my data": choose categories and format, then download within 30 min. */
export function ExportPanel({ patientId }: { patientId: string }) {
  const { t } = useTranslation('common');
  const { showToast } = useToast();
  const { exports, request } = useExports(patientId);
  const cooldown = useCooldown();
  const [chosen, setChosen] = useState<Set<DataCategory>>(
    () => new Set(CATEGORIES)
  );
  const [format, setFormat] = useState<ExportFormat>('pdf');
  const [noneChosen, setNoneChosen] = useState(false);
  // 'new' for the form, or the id of the export being created again.
  const [busy, setBusy] = useState<string | null>(null);

  const recent = exports.slice(0, RECENT);
  const now = useNow(recent.some((e) => isPending(e) || e.status === 'ready'));

  function toggle(category: DataCategory) {
    setNoneChosen(false);
    setChosen((previous) => {
      const next = new Set(previous);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  }

  async function start(exportRequest: ExportRequest, key: string) {
    setBusy(key);
    try {
      await request(exportRequest);
    } catch (error) {
      if (!cooldown.trigger(error)) {
        showToast({ variant: 'error', title: t('export.requestFailed') });
      }
    } finally {
      setBusy(null);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (chosen.size === 0) {
      setNoneChosen(true);
      return;
    }
    void start(
      {
        categories: CATEGORIES.filter((c) => chosen.has(c)),
        format,
        language: exportLanguage(),
      },
      'new'
    );
  }

  function regenerate(previous: DataExport) {
    void start(
      {
        categories: previous.categories,
        format: previous.format,
        language: exportLanguage(),
      },
      previous.id
    );
  }

  return (
    <Card className="mt-4">
      <h2 className="font-display text-base font-semibold text-ink-900">
        {t('export.title')}
      </h2>
      <p className="mt-1 text-sm text-ink-600">{t('export.description')}</p>

      <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
        <fieldset>
          <legend className="font-sans text-sm font-medium text-ink-900">
            {t('export.include')}
          </legend>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {CATEGORIES.map((category) => (
              <Checkbox
                key={category}
                id={`export-${category}`}
                checked={chosen.has(category)}
                onChange={() => toggle(category)}
                label={t(`category.${category}`)}
              />
            ))}
          </div>
          {noneChosen && (
            <p className="mt-2 text-sm text-coral-500">
              {t('export.chooseCategory')}
            </p>
          )}
        </fieldset>

        <fieldset>
          <legend className="font-sans text-sm font-medium text-ink-900">
            {t('export.format')}
          </legend>
          <div className="mt-2 flex gap-2">
            {FORMATS.map((option) => (
              <label
                key={option}
                className={cn(
                  'flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-2 text-sm transition-colors',
                  format === option
                    ? 'border-primary-600 bg-primary-50 text-ink-900'
                    : 'border-ink-400/25 text-ink-600 hover:bg-primary-50/50'
                )}
              >
                <input
                  type="radio"
                  name="export-format"
                  value={option}
                  checked={format === option}
                  onChange={() => setFormat(option)}
                  className="h-4 w-4 accent-primary-600"
                />
                {t(`export.${option}`)}
              </label>
            ))}
          </div>
        </fieldset>

        <CooldownNotice seconds={cooldown.secondsLeft} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-ink-400">{t('export.window')}</p>
          <Button
            type="submit"
            isLoading={busy === 'new'}
            disabled={cooldown.active}
          >
            {t('export.submit')}
          </Button>
        </div>
      </form>

      <h3 className="mt-6 font-sans text-sm font-medium text-ink-900">
        {t('export.recent')}
      </h3>
      {recent.length === 0 ? (
        <p className="mt-2 text-sm text-ink-400">{t('export.none')}</p>
      ) : (
        <ul className="mt-1 divide-y divide-ink-400/15">
          {recent.map((dataExport) => (
            <ExportItem
              key={dataExport.id}
              dataExport={dataExport}
              now={now}
              // A single-record export is made again from its record.
              onRegenerate={
                dataExport.single_record || cooldown.active
                  ? undefined
                  : () => regenerate(dataExport)
              }
              isRegenerating={busy === dataExport.id}
            />
          ))}
        </ul>
      )}
    </Card>
  );
}
