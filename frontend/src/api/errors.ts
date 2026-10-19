/** A non-2xx response from the backend, keeping the status for callers. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** HTTP 429, with the wait the backend asked for when it sent one. */
export class RateLimited extends ApiError {
  readonly retryAfter: number | null;

  constructor(retryAfter: number | null) {
    super('Too many attempts', 429);
    this.retryAfter = retryAfter;
  }
}

/** Builds a RateLimited from a 429 response's Retry-After (seconds). */
export function rateLimitedFrom(res: Response): RateLimited {
  const wait = Number(res.headers.get('Retry-After'));
  return new RateLimited(Number.isFinite(wait) && wait > 0 ? wait : null);
}

export const isUnauthorized = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 401;
