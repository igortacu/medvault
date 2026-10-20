import { useState } from 'react';
import { FileDown, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { MedicalRecord } from '../../api/types';
import { Button } from '../../components/Button';
import { CooldownNotice } from '../../components/CooldownNotice';
import { useCooldown } from '../../hooks/useCooldown';
import { ExportDownload } from './ExportItem';
import {
  exportLanguage,
  isPending,
  recordScopeRef,
  secondsLeft,
  useExports,
  useNow,
} from './useExports';

/** "Export as PDF" for the record shown in the detail dialog. */
export function RecordExportButton({
  record,
  patientId,
}: {
  record: MedicalRecord;
  patientId: string;
}) {
  const { t } = useTranslation('common');
  const { exports, request } = useExports(patientId);
  const cooldown = useCooldown();
  const [exportId, setExportId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [starting, setStarting] = useState(false);

  const current = exports.find((e) => e.id === exportId) ?? null;
  const now = useNow(current !== null);
  const scopeRef = recordScopeRef(record);
  if (!scopeRef || !record.category) return null;

  async function start() {
    setStarting(true);
    setFailed(false);
    try {
      const created = await request({
        categories: [record.category!],
        format: 'pdf',
        language: exportLanguage(),
        scopeRef: scopeRef!,
      });
      setExportId(created.id);
    } catch (error) {
      if (!cooldown.trigger(error)) setFailed(true);
    } finally {
      setStarting(false);
    }
  }

  const ready = current !== null && secondsLeft(current, now) > 0;
  const pending = starting || (current !== null && isPending(current));
  const jobFailed = failed || current?.status === 'failed';

  return (
    <div className="space-y-2">
      {ready ? (
        <div className="space-y-1">
          <p className="text-sm text-ink-600">{t('export.recordReady')}</p>
          <ExportDownload dataExport={current} now={now} />
        </div>
      ) : pending ? (
        <span className="inline-flex items-center gap-2 text-sm text-ink-600">
          <Loader2 size={14} className="animate-spin" aria-hidden />
          {t('export.preparing')}
        </span>
      ) : (
        <Button
          size="sm"
          variant="outline"
          disabled={cooldown.active}
          onClick={() => void start()}
        >
          <FileDown size={14} aria-hidden />
          {jobFailed ? t('export.tryAgain') : t('export.exportRecord')}
        </Button>
      )}
      {jobFailed && !pending && (
        <p className="text-sm text-coral-500">{t('export.failed')}</p>
      )}
      <CooldownNotice seconds={cooldown.secondsLeft} />
    </div>
  );
}
