"""Live institutional aggregation for one patient + category (Epic 2, story 0).

For every active connection the caller may see (RLS for the owner, the narrow
`caregiver_visible_connections` function for a permitted caregiver) this resolves the
FHIR resource types for the category, calls all institutions in parallel, normalises the
rows and reports a per-source status so a slow or failing institution degrades only its
own rows. Nothing institutional is persisted. The only writes are token refreshes and
`last_fetched_at` (owner requests only) plus one `institution.fetch` audit entry per
connection; the caller commits.

Source statuses: ok, timeout, unauthorised, unavailable, needs_reconnect (the connection
was granted before this category's FHIR scopes existed).
"""
import asyncio
import importlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text

from app.aggregation import client, mapping
from app.audit.logger import write_audit_log
from app.models.institution import Institution, InstitutionConnection

# The package re-exports its APIRouter as `router`, shadowing the submodule, so the
# module (token crypto, endpoint resolution) is imported by name.
institutions = importlib.import_module("app.institutions.router")

log = logging.getLogger("medvault.aggregation")

# No institution may hold the page longer than this, whatever its retries add up to.
SOURCE_DEADLINE_SECONDS = 12.0
# A token refresh is a single small request; it must not stall the page for 10 s.
REFRESH_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
TOKEN_LEEWAY = timedelta(seconds=30)


class SourceStatus(BaseModel):
    institution_id: UUID
    institution: str
    status: str
    count: int = 0


async def _rebind(ctx) -> None:
    """Restore the RLS user after a commit/rollback: `app.current_user_id` is set with
    is_local=true, so it vanishes with the transaction that carried it."""
    await ctx.db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(ctx.user_id)},
    )


def _fresh(ciphertext, expires) -> bool:
    return bool(ciphertext and expires and expires > datetime.now(UTC) + TOKEN_LEEWAY)


async def _release(ctx) -> None:
    """End the transaction (dropping the row lock) and re-establish the user context."""
    await ctx.db.commit()
    await _rebind(ctx)


async def _token(ctx, row, institution: Institution, http, is_owner: bool) -> str:
    """A usable access token, refreshing (owner only) when it is about to expire.

    Institutions rotate refresh tokens, so two requests refreshing at once would burn
    each other's token and the loser would wrongly look revoked. The connection row is
    locked (`FOR UPDATE`) for the refresh; a request that waited for the lock finds the
    new token already committed and just uses it. The lock is released by committing right
    after the refresh. Only a definitive `invalid_grant` marks the connection `expired`:
    timeouts, 5xx and our own misconfiguration are reported as plain failures."""
    if _fresh(row.access_token_ciphertext, row.access_token_expires_at):
        return institutions._decrypt(row.access_token_ciphertext)
    if not is_owner or not row.refresh_token_ciphertext:
        # A caregiver cannot persist a rotated refresh token, so only the owner refreshes.
        raise client.SourceFailure("unauthorised" if is_owner else "unavailable")

    connection = (
        await ctx.db.execute(
            select(InstitutionConnection)
            .where(InstitutionConnection.id == row.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    try:
        if connection is None or connection.status != "active":
            raise client.SourceFailure("unavailable")
        if _fresh(connection.access_token_ciphertext, connection.access_token_expires_at):
            return institutions._decrypt(connection.access_token_ciphertext)
        if not connection.refresh_token_ciphertext:
            connection.status = "expired"
            raise client.SourceFailure("unauthorised")

        try:
            response = await http.post(
                institutions._endpoint(institution, "token"),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": institutions._decrypt(connection.refresh_token_ciphertext),
                },
                auth=(institution.oauth_client_id, institutions._client_secret(institution)),
                timeout=REFRESH_TIMEOUT,
            )
        except httpx.TimeoutException:
            raise client.SourceFailure("timeout")
        except httpx.HTTPError:
            raise client.SourceFailure("unavailable")
        if response.status_code in (400, 401):
            connection.status = "expired"  # the grant itself was refused
            raise client.SourceFailure("unauthorised")
        if response.status_code >= 400:
            raise client.SourceFailure("unavailable")
        try:
            tokens = response.json()
            access = tokens["access_token"]
        except (ValueError, KeyError, TypeError):
            raise client.SourceFailure("unavailable")

        connection.access_token_ciphertext = institutions._encrypt(access)
        connection.access_token_expires_at = datetime.now(UTC) + timedelta(
            seconds=int(tokens.get("expires_in", 900))
        )
        if tokens.get("refresh_token"):
            connection.refresh_token_ciphertext = institutions._encrypt(
                tokens["refresh_token"]
            )
        return access
    finally:
        # Persist whatever changed (new tokens, or `expired`) and drop the lock.
        await _release(ctx)


async def _fetch_source(
    http, institution: Institution, token: str, resource_types: list[str], category: str
) -> tuple[str, list[dict]]:
    base = institutions._endpoint(institution, "fhir")
    results = await asyncio.gather(
        *(
            client.search(
                http,
                institution_key=institution.external_id,
                fhir_base=base,
                token=token,
                resource_type=rtype,
            )
            for rtype in resource_types
        ),
        return_exceptions=True,
    )
    items: list[dict] = []
    status = "ok"
    breaker_hit = False
    for result in results:
        if isinstance(result, client.SourceFailure):
            # Keep the most informative failure; an auth problem outranks a timeout.
            if status == "ok" or result.status == "unauthorised":
                status = result.status
            if result.status != "unauthorised" and not result.short_circuit:
                breaker_hit = True
        elif isinstance(result, BaseException):
            log.error("Unexpected aggregation error: %s", type(result).__name__)
            breaker_hit = True
            if status == "ok":
                status = "unavailable"
        else:
            for resource in result:
                try:
                    row = mapping.normalize(
                        category,
                        resource,
                        external_id=institution.external_id,
                        institution_name=institution.name,
                    )
                except Exception:  # a malformed record is skipped, never fatal
                    log.warning("Skipped a malformed %s record", category)
                    continue
                if row:
                    items.append(row)
    # One breaker verdict per fetch of the source, not per resource type.
    if breaker_hit:
        client.record_failure(institution.external_id)
    elif status == "ok":
        client.record_success(institution.external_id)
    return status, items


async def fetch_institutional(
    ctx, category: str, patient_id: UUID, http: httpx.AsyncClient | None = None
) -> tuple[list[dict], list[SourceStatus]]:
    actor = UUID(str(ctx.user_id))
    is_owner = actor == patient_id
    rows = (
        await ctx.db.execute(
            text(
                "SELECT * FROM medvault.caregiver_visible_connections("
                "CAST(:p AS uuid), CAST(:c AS medvault.data_category))"
            ),
            {"p": str(patient_id), "c": category},
        )
    ).all()
    if not rows:
        return [], []

    institution_rows = (
        await ctx.db.execute(
            select(Institution).where(Institution.id.in_([r.institution_id for r in rows]))
        )
    ).scalars().all()
    by_id = {i.id: i for i in institution_rows}

    owned_http = http is None
    http = http or httpx.AsyncClient(timeout=client.TIMEOUT, follow_redirects=False)
    try:
        # Tokens first, sequentially: refresh uses the shared DB session.
        plans = []  # (row, institution, token | None, resource_types, early_status)
        for row in rows:
            institution = by_id.get(row.institution_id)
            if institution is None:
                continue
            granted = set(row.granted_scopes or [])
            types = [
                t
                for t in mapping.CATEGORY_RESOURCE_TYPES[category]
                if mapping.scope_for(t) in granted
            ]
            if not types:
                plans.append((row, institution, None, [], "needs_reconnect"))
                continue
            try:
                token = await _token(ctx, row, institution, http, is_owner)
                plans.append((row, institution, token, types, None))
            except client.SourceFailure as failure:
                plans.append((row, institution, None, [], failure.status))
            except Exception as error:  # decrypt/config/DB trouble: this source only
                log.error("Token step failed: %s", type(error).__name__)
                plans.append((row, institution, None, [], "unavailable"))

        # Give the pooled DB connection back while we wait on the institutions; the
        # slowest one can take ~12 s and must not pin a connection for that long.
        await ctx.db.commit()

        async def run(plan):
            _, institution, token, types, early = plan
            if early:
                return early, []
            try:
                return await asyncio.wait_for(
                    _fetch_source(http, institution, token, types, category),
                    SOURCE_DEADLINE_SECONDS,
                )
            except asyncio.TimeoutError:
                client.record_failure(institution.external_id)
                return "timeout", []
            except Exception as error:
                log.error("Source fetch failed: %s", type(error).__name__)
                return "unavailable", []

        outcomes = await asyncio.gather(*(run(p) for p in plans))
    finally:
        if owned_http:
            await http.aclose()

    await _rebind(ctx)
    items: list[dict] = []
    sources: list[SourceStatus] = []
    for (row, institution, _, _, _), (status, source_items) in zip(plans, outcomes):
        items += source_items
        sources.append(
            SourceStatus(
                institution_id=institution.id,
                institution=institution.name,
                status=status,
                count=len(source_items),
            )
        )
        if is_owner and status == "ok":
            connection = await ctx.db.get(InstitutionConnection, row.id)
            if connection is not None:
                connection.last_fetched_at = datetime.now(UTC)
        await write_audit_log(
            ctx.db,
            actor_user_id=actor,
            subject_patient_id=patient_id,
            action="institution.fetch",
            resource_type=f"category:{category}",
            resource_id=row.id,
            institution_id=institution.id,
            outcome="success" if status == "ok" else "failure",
            metadata={"status": status, "result_count": len(source_items)},
        )
    return items, sources
