import type { MedicalRecord } from '../../api/types.ts';
import { useEffect, useState } from 'react';
import { datasetApi } from '../../api';
import { ApiError } from '../../api/errors.ts';
import i18n from '../../i18n';
type OriginalState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; url: string };

/**
 * Fetches the signed original-file URL for a self-uploaded document whenever
 * the modal opens on it. Institutional records have no original file to
 * fetch (§0 of the app schema never persists institutional bytes), so this
 * only runs for `source === 'self_uploaded'`.
 */
export default function useOriginalDocument(
  record: MedicalRecord | null,
  open: boolean
): OriginalState {
  const [state, setState] = useState<OriginalState>({ status: 'idle' });

  useEffect(() => {
    if (!open || !record || record.source !== 'self_uploaded') {
      setState({ status: 'idle' });
      return;
    }

    let cancelled = false;
    setState({ status: 'loading' });

    datasetApi
      .getOriginalDocument(record.id)
      .then(({ url }) => {
        if (!cancelled) setState({ status: 'ready', url });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: 'error',
            // Not the raw error: it carries backend or developer wording.
            message:
              error instanceof ApiError && error.status === 403
                ? i18n.t('documents:detail.originalNoAccess')
                : i18n.t('documents:detail.originalUnavailable'),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [record, open]);

  return state;
}
