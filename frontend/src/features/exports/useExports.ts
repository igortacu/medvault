import { useCallback, useEffect, useState } from 'react';
import { datasetApi } from '../../api';
import type { DataExport, ExportRequest, MedicalRecord } from '../../api/types';
import i18n from '../../i18n';

const PENDING: DataExport['status'][] = ['requested', 'processing'];
const POLL_MS = 2000;

export const isPending = (exp: DataExport) => PENDING.includes(exp.status);

/** The scope_ref the backend uses to find one record, if it can export it. */
export function recordScopeRef(record: MedicalRecord): string | null {
  if (record.source === 'self_uploaded') return `document:${record.id}`;
  return record.originalRef ?? null;
}

/** Seconds left in a ready export's download window (0 once it has passed). */
export function secondsLeft(exp: DataExport, now: number): number {
  if (exp.status !== 'ready' || !exp.expires_at) return 0;
  return Math.max(0, Math.ceil((Date.parse(exp.expires_at) - now) / 1000));
}

/** The language the PDF's headings should use: the interface's own. */
export function exportLanguage(): string {
  const lang = i18n.resolvedLanguage ?? i18n.language;
  return ['ro', 'en', 'ru'].includes(lang) ? lang : 'ro';
}

/** A clock that ticks every second while `active`, for live countdowns. */
export function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
}

/**
 * A patient's recent exports. Polls while one is being generated, so the
 * list turns from "Preparing…" to "Download" by itself.
 */
export function useExports(patientId: string | null) {
  const [exports, setExports] = useState<DataExport[]>([]);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    if (!patientId) return;
    try {
      setExports(await datasetApi.getDataExports(patientId));
    } catch {
      // Keep showing the last list; the next poll or action tries again.
    } finally {
      setLoaded(true);
    }
  }, [patientId]);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    datasetApi
      .getDataExports(patientId)
      .then((list) => {
        if (!cancelled) setExports(list);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  const pending = exports.some(isPending);
  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [pending, refresh]);

  /** Starts an export; throws (e.g. RateLimited) for the caller to handle. */
  const request = useCallback(
    async (exportRequest: ExportRequest): Promise<DataExport> => {
      if (!patientId) throw new Error('No patient');
      const created = await datasetApi.requestExport(patientId, exportRequest);
      setExports((previous) => [
        created,
        ...previous.filter((e) => e.id !== created.id),
      ]);
      return created;
    },
    [patientId]
  );

  return { exports, loaded, request, refresh };
}
