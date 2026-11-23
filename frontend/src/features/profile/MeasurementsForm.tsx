import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '../../components/Card.tsx';
import { Button } from '../../components/Button.tsx';
import { Input } from '../../components/Input.tsx';
import { FormField } from '../../components/Formfield.tsx';
import { useToast } from '../../components/Toast.tsx';
import { useDatasetStore } from '../../store/datasetStore.ts';
import type { PatientProfile } from '../../api/types.ts';
import { parseHeight, parseWeight } from './measurementRules.ts';

function initial(value: number | null): string {
  return value === null ? '' : String(value);
}

/** Edits the logged-in user's own weight and height. */
export function MeasurementsForm({
  profile,
  onDone,
}: {
  profile: PatientProfile;
  onDone: () => void;
}) {
  const { t } = useTranslation(['profile', 'common']);
  const { showToast } = useToast();
  const updateMeasurements = useDatasetStore(
    (state) => state.updateMeasurements
  );

  const [weight, setWeight] = useState(initial(profile.weight_kg));
  const [height, setHeight] = useState(initial(profile.height_cm));
  const [errors, setErrors] = useState<{ weight?: string; height?: string }>(
    {}
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const w = parseWeight(weight);
    const h = parseHeight(height);
    setErrors({
      weight: w.ok ? undefined : w.error,
      height: h.ok ? undefined : h.error,
    });
    if (!w.ok || !h.ok) return;

    // Only send what changed; the backend keeps anything left out.
    const update = {
      ...(w.value !== undefined && w.value !== profile.weight_kg
        ? { weight_kg: w.value }
        : {}),
      ...(h.value !== undefined && h.value !== profile.height_cm
        ? { height_cm: h.value }
        : {}),
    };
    if (Object.keys(update).length === 0) {
      if (w.value === undefined && h.value === undefined) {
        setFormError(t('edit.required'));
        return;
      }
      onDone();
      return;
    }

    setFormError(null);
    setIsSaving(true);
    try {
      await updateMeasurements(update);
      showToast({ variant: 'success', title: t('edit.saved') });
      onDone();
    } catch {
      showToast({
        variant: 'error',
        title: t('edit.saveFailed'),
        description: t('common:pleaseTryAgain'),
      });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card className="mt-4">
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <h2 className="font-sans text-base font-medium text-ink-900">
          {t('edit.title')}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t('edit.weightLabel')} error={errors.weight}>
            <Input
              inputMode="decimal"
              autoComplete="off"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="72.4"
            />
          </FormField>
          <FormField label={t('edit.heightLabel')} error={errors.height}>
            <Input
              inputMode="decimal"
              autoComplete="off"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              placeholder="170.5"
            />
          </FormField>
        </div>
        {formError && (
          <p role="alert" className="text-sm text-coral-500">
            {formError}
          </p>
        )}
        <p className="text-xs text-ink-400">{t('edit.hint')}</p>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onDone}
            disabled={isSaving}
          >
            {t('common:cancel')}
          </Button>
          <Button type="submit" isLoading={isSaving}>
            {t('edit.save')}
          </Button>
        </div>
      </form>
    </Card>
  );
}
