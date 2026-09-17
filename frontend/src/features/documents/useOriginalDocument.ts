import type { MedicalRecord } from '../../api/types.ts';
import { useEffect, useState } from 'react';
import { datasetApi } from '../../api';
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
            message:
              error instanceof Error
                ? error.message
                : 'The original file is unavailable.',
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [record, open]);

  return state;
}
