# Institution mock

Run from the repository root:

```bash
.venv/bin/uvicorn institution_mock.app:app --port 8001
```

The service simulates two institutions with synthetic data. The shared development
IDNP is `2001234567890`; the default client for an institution is
`medvault-{institution_id}` and the default secret is
`DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD`. Override all secrets in a deployed
environment.

OAuth state is intentionally process-local for the single-worker development mock.
Restarting the service invalidates outstanding requests and tokens.
