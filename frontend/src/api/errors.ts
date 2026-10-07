/** A non-2xx response from the backend, keeping the status for callers. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const isUnauthorized = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 401;
