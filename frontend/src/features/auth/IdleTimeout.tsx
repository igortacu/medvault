import { useCallback, useEffect, useRef, useState } from 'react';
import { datasetApi } from '../../api';
import { isUnauthorized } from '../../api/errors.ts';
import { Button } from '../../components/Button.tsx';
import { Modal, ModalContent } from '../../components/Modal.tsx';
import { useDatasetStore } from '../../store/datasetStore.ts';

// Mirrors the backend's sliding 15-minute session (auth/sessions.py).
const IDLE_LIMIT_MS = 15 * 60 * 1000;
const WARNING_MS = 60 * 1000;
// The backend only slides on API calls, so activity pings it at most this often.
const KEEPALIVE_MS = 5 * 60 * 1000;
const ACTIVITY_EVENTS = ['mousedown', 'keydown', 'touchstart', 'scroll'] as const;

/** Warns ~60 s before the session idles out, then signs the user out. */
export function IdleTimeout() {
  const logout = useDatasetStore((s) => s.logout);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const lastActivity = useRef(0);
  const lastPing = useRef(0);
  const warning = secondsLeft !== null;

  const ping = useCallback(() => {
    lastPing.current = Date.now();
    datasetApi.getCurrentUser().catch((error) => {
      // The session ended server-side (8 h cap, password reset elsewhere).
      if (isUnauthorized(error)) useDatasetStore.setState({ needsLogin: true });
    });
  }, []);

  const stayActive = useCallback(() => {
    lastActivity.current = Date.now();
    setSecondsLeft(null);
    ping();
  }, [ping]);

  useEffect(() => {
    lastActivity.current = lastPing.current = Date.now();
    const onActivity = () => {
      // While the warning is up, only the explicit button counts.
      if (Date.now() - lastActivity.current >= IDLE_LIMIT_MS - WARNING_MS) return;
      lastActivity.current = Date.now();
      if (Date.now() - lastPing.current > KEEPALIVE_MS) ping();
    };
    ACTIVITY_EVENTS.forEach((e) =>
      window.addEventListener(e, onActivity, { passive: true })
    );

    const tick = window.setInterval(() => {
      const left = IDLE_LIMIT_MS - (Date.now() - lastActivity.current);
      if (left <= 0) {
        window.clearInterval(tick);
        void logout();
      } else if (left <= WARNING_MS) {
        setSecondsLeft(Math.ceil(left / 1000));
      }
    }, 1000);

    return () => {
      window.clearInterval(tick);
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
    };
  }, [logout, ping]);

  return (
    <Modal open={warning} onOpenChange={(open) => !open && stayActive()}>
      <ModalContent
        title="Still there?"
        description="For your security, you'll be signed out soon because of inactivity."
      >
        <p className="text-sm text-ink-600" aria-live="polite">
          Signing out in {secondsLeft ?? 0}s.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="outline" onClick={() => void logout()}>
            Sign out
          </Button>
          <Button onClick={stayActive}>Stay signed in</Button>
        </div>
      </ModalContent>
    </Modal>
  );
}
