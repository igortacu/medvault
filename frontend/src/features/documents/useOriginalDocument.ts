import type { MedicalRecord } from '../../api/types.ts';
import { useEffect, useState } from 'react';
import { datasetApi } from '../../api';
import { ApiError } from '../../api/errors.ts';
import i18n from '../../i18n';
import { useDatasetStore } from '../../store/datasetStore.ts';

type OriginalState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; url: string; mimeType?: string; inMemory: boolean };

/** Whether the record has an original file the viewer can open. */
export function canOpenOriginal(record: MedicalRecord | null): boolean {
  if (!record) return false;
  return record.source === 'self_uploaded' || Boolean(record.hasOriginal);
}

// Not the raw error: it carries backend or developer wording.
function messageFor(error: unknown): string {
  const status = error instanceof ApiError ? error.status : 0;
  if (status === 403) return i18n.t('documents:detail.originalNoAccess');
  if (status === 409) return i18n.t('documents:detail.originalReconnect');
  if (status === 502) return i18n.t('documents:detail.originalUnreachable');
  return i18n.t('documents:detail.originalUnavailable');
}

/**
 * Loads a record's original file whenever the modal opens on it.
 *
 * Self-uploads come back as a short-lived signed URL. An institutional
 * record's original is streamed live from the institution through the
 * backend (never stored) and kept only in memory as a blob URL, which is
 * released when the modal closes.
 */
export default function useOriginalDocument(
  record: MedicalRecord | null,
  open: boolean
): OriginalState {
  const patientId = useDatasetStore((state) => state.patientId);
  const [state, setState] = useState<OriginalState>({ status: 'idle' });

  useEffect(() => {
    if (!open || !record || !canOpenOriginal(record)) {
      setState({ status: 'idle' });
      return;
    }

    let cancelled = false;
    let blobUrl: string | null = null;
    setState({ status: 'loading' });

    const load: Promise<OriginalState> =
      record.source === 'self_uploaded'
        ? datasetApi.getOriginalDocument(record.id).then(({ url }) => ({
            status: 'ready',
            url,
            mimeType: record.mimeType,
            inMemory: false,
          }))
        : datasetApi
            .getInstitutionalOriginal(record, patientId ?? '')
            .then((blob) => {
              blobUrl = URL.createObjectURL(blob);
              return {
                status: 'ready',
                url: blobUrl,
                mimeType: blob.type,
                inMemory: true,
              };
            });

    load
      .then((ready) => {
        if (!cancelled) setState(ready);
        // Closed before the file arrived: release it straight away.
        else if (ready.status === 'ready' && ready.inMemory) {
          URL.revokeObjectURL(ready.url);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setState({ status: 'error', message: messageFor(error) });
      });

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [record, open, patientId]);

  return state;
}
