#!/bin/sh
# Check the dependencies for known vulnerabilities (OWASP A03). Needs Docker only.
# Exits non-zero if the Python packages have any advisory, or the packages shipped to
# the browser have one rated high or critical. Dev-only npm tooling is listed, not failed.
cd "$(dirname "$0")/.." || exit 2
status=0

echo "== Python: backend and institution mock"
docker run --rm -v "$PWD:/repo:ro" -w /repo python:3.11-slim sh -c '
  pip install --quiet --root-user-action=ignore --disable-pip-version-check pip-audit &&
  pip-audit --progress-spinner off -r backend/requirements.txt &&
  pip-audit --progress-spinner off -r institution_mock/requirements.txt
' || status=1

echo "== npm: packages shipped to the browser"
docker run --rm -v "$PWD/frontend:/app:ro" -w /app node:22-slim \
  npm audit --omit=dev --audit-level=high --no-fund || status=1

echo "== npm: all packages, including dev tooling (informational)"
docker run --rm -v "$PWD/frontend:/app:ro" -w /app node:22-slim \
  npm audit --audit-level=none --no-fund | tail -4

[ "$status" -eq 0 ] && echo "No blocking vulnerabilities." || echo "Vulnerabilities found."
exit "$status"
