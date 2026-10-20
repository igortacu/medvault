import { Download, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { datasetApi } from '../../api';
import type { DataExport } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { formatWait } from '../../hooks/useCooldown';
import { cn } from '../../lib/cn';
import { formatDate } from '../../utils/formatDate';
import { isPending, secondsLeft } from './useExports';

const ALL_CATEGORIES = 6;

export const downloadLinkClass =
  'inline-flex h-8 items-center justify-center gap-2 rounded-pill bg-primary-600 px-3 font-sans text-sm font-medium text-white transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2';

/** The download link of a ready export, plus its live countdown. */
export function ExportDownload({
  dataExport,
  now,
  className,
}: {
  dataExport: DataExport;
  now: number;
  className?: string;
}) {
  const { t } = useTranslation('common');
  const left = secondsLeft(dataExport, now);
  if (left <= 0) return null;
  return (
    <div className={cn('flex flex-wrap items-center gap-3', className)}>
      <a
        href={datasetApi.exportFileUrl(dataExport)}
        download={`medvault-export.${dataExport.format}`}
        className={downloadLinkClass}
      >
        <Download size={14} aria-hidden />
        {t('export.download')}
      </a>
      <span className="text-xs text-ink-400" role="timer" aria-live="off">
        {t('export.availableFor', { time: formatWait(left) })}
      </span>
    </div>
  );
}

interface ExportItemProps {
  dataExport: DataExport;
  now: number;
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

/** One export in the "Recent exports" list. */
export function ExportItem({
  dataExport,
  now,
  onRegenerate,
  isRegenerating,
}: ExportItemProps) {
  const { t } = useTranslation('common');
  const expired =
    dataExport.status === 'expired' ||
    (dataExport.status === 'ready' && secondsLeft(dataExport, now) <= 0);
  const what = dataExport.single_record
    ? t('export.singleRecord')
    : dataExport.categories.length >= ALL_CATEGORIES
      ? t('export.allData')
      : t('export.categories', { count: dataExport.categories.length });

  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-900">
          {what}
          <Badge variant="neutral">{t(`export.${dataExport.format}`)}</Badge>
        </p>
        <p className="text-xs text-ink-400">
          {t('export.requested', { time: formatDate(dataExport.created_at) })}
        </p>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-3">
        {isPending(dataExport) && (
          <span className="inline-flex items-center gap-2 text-sm text-ink-600">
            <Loader2 size={14} className="animate-spin" aria-hidden />
            {t('export.preparing')}
          </span>
        )}
        {dataExport.status === 'ready' && !expired && (
          <ExportDownload dataExport={dataExport} now={now} />
        )}
        {(expired || dataExport.status === 'failed') && (
          <>
            <span
              className={cn(
                'text-sm',
                expired ? 'text-ink-400' : 'text-coral-500'
              )}
            >
              {expired ? t('export.expired') : t('export.failed')}
            </span>
            {onRegenerate && (
              <Button
                size="sm"
                variant="outline"
                isLoading={isRegenerating}
                onClick={onRegenerate}
              >
                {expired ? t('export.regenerate') : t('export.tryAgain')}
              </Button>
            )}
          </>
        )}
      </div>
    </li>
  );
}
