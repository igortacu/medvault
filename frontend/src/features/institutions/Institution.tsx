import { Building2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import type {
  Institution as InstitutionRecord,
  InstitutionConnection,
} from '../../api/types';
import { formatDate } from '../../utils/formatDate';
import {
  canReconnect,
  scopeLabels,
  statusPresentation,
} from './connectionRules';

export interface InstitutionProps {
  institution: InstitutionRecord;
  connection: InstitutionConnection;
  onReconnect: () => void;
  onDisconnect: () => void;
}

/** One connected (or attempted) institution with its status and actions. */
function Institution({
  institution,
  connection,
  onReconnect,
  onDisconnect,
}: InstitutionProps) {
  const { t } = useTranslation('institutions');
  const status = statusPresentation(connection);
  const access = scopeLabels(connection.granted_scopes);

  return (
    <Card className="flex flex-col gap-4 sm:flex-row sm:items-start">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
        <Building2 size={20} aria-hidden />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-sans text-sm font-medium text-ink-900">
            {institution.name}
          </p>
          <Badge variant={status.tone}>{status.label}</Badge>
        </div>
        <p className="mt-0.5 text-sm text-ink-400">
          {t(`type.${institution.type}`)}
          {institution.city && ` · ${institution.city}`}
        </p>

        {status.explanation && (
          <p className="mt-2 text-sm text-ink-600">{status.explanation}</p>
        )}

        {connection.status === 'active' && (
          <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {connection.connected_at && (
              <div>
                <dt className="text-xs text-ink-400">{t('card.connected')}</dt>
                <dd className="text-ink-900">
                  {formatDate(connection.connected_at)}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-ink-400">{t('card.lastFetched')}</dt>
              <dd className="text-ink-900">
                {connection.last_fetched_at
                  ? formatDate(connection.last_fetched_at)
                  : t('card.notYet')}
              </dd>
            </div>
            {access.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-ink-400">{t('card.shared')}</dt>
                <dd className="text-ink-900">{access.join(', ')}</dd>
              </div>
            )}
          </dl>
        )}
      </div>

      <div className="flex shrink-0 gap-2 sm:flex-col sm:items-end">
        {canReconnect(connection) && (
          <Button size="sm" variant="outline" onClick={onReconnect}>
            {connection.status === 'no_match'
              ? t('card.tryAgain')
              : t('card.reconnect')}
          </Button>
        )}
        {connection.status === 'active' && (
          <Button size="sm" variant="ghost" onClick={onDisconnect}>
            {t('card.disconnect')}
          </Button>
        )}
      </div>
    </Card>
  );
}

export default Institution;
