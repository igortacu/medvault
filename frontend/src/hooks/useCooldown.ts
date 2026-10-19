import { useCallback, useEffect, useState } from 'react';
import { RateLimited } from '../api/errors';

/** Wait shown when a 429 arrives without a Retry-After. */
const FALLBACK_SECONDS = 60;

/** "4:05", or "1:02:03" past an hour. */
export function formatWait(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(seconds % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

/**
 * Live cooldown after the backend answers 429. `trigger(error)` starts it from
 * the error's Retry-After and returns false for any other error, so callers
 * keep their own handling for those. Counts against the wall clock, so a tab
 * left in the background still shows the right wait when it comes back.
 */
export function useCooldown() {
  const [until, setUntil] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(0);

  const start = useCallback((seconds: number) => {
    const wait = Math.max(1, Math.ceil(seconds));
    setUntil(Date.now() + wait * 1000);
    setSecondsLeft(wait);
  }, []);

  useEffect(() => {
    if (!until) return;
    const timer = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) setUntil(0);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [until]);

  const trigger = useCallback(
    (error: unknown): boolean => {
      if (!(error instanceof RateLimited)) return false;
      start(error.retryAfter ?? FALLBACK_SECONDS);
      return true;
    },
    [start]
  );

  return { secondsLeft, active: secondsLeft > 0, start, trigger };
}
