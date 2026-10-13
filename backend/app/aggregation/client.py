"""Outbound FHIR reads with the D11 resilience rules (Epic 2, story 0).

4 s connect / 10 s read timeouts, one retry with backoff on a timeout, connection
error or 5xx, and a small in-process circuit breaker per institution so a dead
institution stops costing every page load ~10 s. 401/403 are reported as
"unauthorised" and never retried or counted against the breaker.
"""
import asyncio
import time

import httpx

TIMEOUT = httpx.Timeout(10.0, connect=4.0)
RETRY_BACKOFF_SECONDS = 0.3
BREAKER_THRESHOLD = 3
BREAKER_OPEN_SECONDS = 30.0
PAGE_SIZE = 100
MAX_PAGES = 5


def _same_origin_under(url: str, base: str) -> bool:
    """A `next` link is institution-controlled data: follow it only within the FHIR base."""
    try:
        target, root = httpx.URL(url), httpx.URL(base)
    except httpx.InvalidURL:
        return False
    prefix = root.path.rstrip("/") + "/"
    return (
        target.scheme == root.scheme
        and target.host == root.host
        and target.port == root.port
        and target.path.startswith(prefix)
    )


class SourceFailure(Exception):
    """A failed institution read. `status` is timeout / unauthorised / unavailable."""

    def __init__(self, status: str, *, short_circuit: bool = False):
        super().__init__(status)
        self.status = status
        # True when the breaker refused the call without touching the network.
        self.short_circuit = short_circuit


# institution key -> (consecutive failures, breaker open until monotonic time)
_breaker: dict[str, tuple[int, float]] = {}


def reset_breakers() -> None:
    _breaker.clear()


def _breaker_open(key: str) -> bool:
    _, open_until = _breaker.get(key, (0, 0.0))
    return time.monotonic() < open_until


def record_success(key: str) -> None:
    """A whole source answered cleanly: close its breaker."""
    _breaker.pop(key, None)


def record_failure(key: str) -> None:
    """One failed source fetch (any resource type, or the deadline). Counted once per
    fetch so a single flaky resource type cannot flap the breaker."""
    failures, _ = _breaker.get(key, (0, 0.0))
    failures += 1
    open_until = (
        time.monotonic() + BREAKER_OPEN_SECONDS if failures >= BREAKER_THRESHOLD else 0.0
    )
    _breaker[key] = (failures, open_until)


async def _get(http: httpx.AsyncClient, url: str, token: str, params: dict | None) -> dict:
    last: SourceFailure | None = None
    for attempt in range(2):
        if attempt:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)
        try:
            response = await http.get(
                url, params=params, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.TimeoutException:
            last = SourceFailure("timeout")
            continue
        except httpx.HTTPError:
            last = SourceFailure("unavailable")
            continue
        if response.status_code in (401, 403):
            raise SourceFailure("unauthorised")
        if response.status_code >= 500:
            last = SourceFailure("unavailable")
            continue
        if response.status_code >= 400:
            raise SourceFailure("unavailable")
        try:
            return response.json()
        except ValueError:
            raise SourceFailure("unavailable")
    raise last or SourceFailure("unavailable")


async def search(
    http: httpx.AsyncClient,
    *,
    institution_key: str,
    fhir_base: str,
    token: str,
    resource_type: str,
) -> list[dict]:
    """All resources of one type the token's patient may read, following `next` links."""
    if _breaker_open(institution_key):
        raise SourceFailure("unavailable", short_circuit=True)
    url: str | None = f"{fhir_base}/{resource_type}"
    params: dict | None = {"_count": PAGE_SIZE}
    resources: list[dict] = []
    try:
        for _ in range(MAX_PAGES):
            bundle = await _get(http, url, token, params)
            resources += [
                e["resource"]
                for e in bundle.get("entry", [])
                if isinstance(e.get("resource"), dict)
            ]
            url = next(
                (
                    link.get("url")
                    for link in bundle.get("link", [])
                    if link.get("relation") == "next"
                ),
                None,
            )
            params = None
            if not url:
                break
            if not _same_origin_under(url, fhir_base):
                raise SourceFailure("unavailable")
    except SourceFailure:
        raise
    return resources
