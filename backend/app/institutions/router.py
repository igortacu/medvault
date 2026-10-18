import asyncio
import base64
import hashlib
import json
import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.aggregation.mapping import ALL_RESOURCE_TYPES
from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.database import redis_client
from app.models.institution import Institution, InstitutionConnection

router = APIRouter(tags=["institutions"])
CALLBACK_URL = os.getenv(
    "INSTITUTION_CALLBACK_URL",
    "http://localhost:8000/api/v1/institutions/callback",
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
MOCK_BASE_URL = os.getenv("INSTITUTION_MOCK_BASE_URL", "").rstrip("/")
# Where the browser reaches the mock's /authorize page, when that differs from the
# address the backend calls (e.g. a container name under docker compose).
MOCK_PUBLIC_URL = os.getenv("INSTITUTION_MOCK_PUBLIC_URL", "").rstrip("/") or MOCK_BASE_URL
OAUTH_STATE_TTL = 120
REQUESTED_SCOPES = (
    "patient/Patient.read",
    "patient/Observation.read",
    *(f"patient/{t}.read" for t in ALL_RESOURCE_TYPES),
    "offline_access",
)


class InstitutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    name: str
    type: str
    city: str | None


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    status: str
    origin: str
    granted_scopes: list[str] | None
    failure_reason: str | None
    consented_at: datetime | None
    connected_at: datetime | None
    last_fetched_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ConnectRequest(BaseModel):
    idnp: str = Field(pattern=r"^[0-9]{13}$")
    consent_text_version: str = Field(min_length=1, max_length=50)


class ConnectPublicRequest(ConnectRequest):
    # The public institutions the patient ticked; omitted means all of them.
    institution_ids: list[UUID] | None = Field(default=None, min_length=1)


class ConnectResponse(BaseModel):
    connection_id: UUID
    authorize_url: str


class ConnectionAttempt(BaseModel):
    connection_id: UUID
    institution_id: UUID
    status: str


class ConnectPublicResponse(BaseModel):
    # None when every public institution is already connected or none could be
    # reached; the attempts then say what happened to each one.
    authorize_url: str | None
    connections: list[ConnectionAttempt]


class PushedAuthorization(BaseModel):
    state: str
    code_verifier: str
    authorize_url: str


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        yield client


def _endpoint(institution: Institution, endpoint: str) -> str:
    if MOCK_BASE_URL:
        suffix = "fhir" if endpoint == "fhir" else f"oauth/{endpoint}"
        base = MOCK_PUBLIC_URL if endpoint == "authorize" else MOCK_BASE_URL
        return f"{base}/{institution.external_id}/{suffix}"
    return {
        "par": institution.par_url,
        "authorize": institution.authorize_url,
        "token": institution.token_url,
        "revoke": institution.revoke_url,
        "fhir": institution.fhir_base_url,
    }[endpoint]


def _client_secret(institution: Institution) -> str:
    if institution.oauth_secret_key_version == 0:
        return institution.oauth_client_secret_ciphertext.decode()
    return _decrypt(institution.oauth_client_secret_ciphertext)


def _cipher() -> Fernet:
    key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Token encryption is not configured"
        )
    try:
        return Fernet(key.encode())
    except ValueError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Token encryption is misconfigured"
        )


def _encrypt(value: str) -> bytes:
    return _cipher().encrypt(value.encode())


def _decrypt(value: bytes) -> str:
    try:
        return _cipher().decrypt(value).decode()
    except InvalidToken:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Stored token cannot be decrypted"
        )


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


async def _post_oauth(
    client: httpx.AsyncClient,
    url: str,
    institution: Institution,
    data: dict[str, str],
) -> dict:
    try:
        response = await client.post(
            url,
            data=data,
            auth=(institution.oauth_client_id, _client_secret(institution)),
        )
        response.raise_for_status()
        return response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Institution authorization service unavailable"
        ) from error


async def _active_connection(
    ctx: RequestContext, connection_id: UUID
) -> InstitutionConnection:
    connection = await ctx.db.scalar(
        select(InstitutionConnection)
        .options(joinedload(InstitutionConnection.institution))
        .where(InstitutionConnection.id == connection_id)
    )
    if connection is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Institution connection not found"
        )
    return connection


@router.get("/institutions", response_model=list[InstitutionResponse])
async def list_institutions(ctx: RequestContext = Depends(get_request_context)):
    institutions = (
        await ctx.db.scalars(
            select(Institution)
            .where(Institution.is_active.is_(True))
            .order_by(Institution.name)
        )
    ).all()
    return institutions


@router.get("/institution-connections", response_model=list[ConnectionResponse])
async def list_connections(ctx: RequestContext = Depends(get_request_context)):
    return (
        await ctx.db.scalars(
            select(InstitutionConnection).order_by(
                InstitutionConnection.created_at.desc()
            )
        )
    ).all()


async def _live_connection(
    ctx: RequestContext, institution_id: UUID
) -> InstitutionConnection | None:
    connection = await ctx.db.scalar(
        select(InstitutionConnection).where(
            InstitutionConnection.institution_id == institution_id,
            InstitutionConnection.status.in_(
                ("pending_consent", "authorizing", "active")
            ),
        )
    )
    # An authorization whose OAuth state has expired can never complete (the
    # patient closed the tab, or the chain broke), so it must not block a retry.
    if (
        connection is not None
        and connection.status == "authorizing"
        and connection.consented_at is not None
        and connection.consented_at
        < datetime.now(UTC) - timedelta(seconds=OAUTH_STATE_TTL)
    ):
        connection.status = "error"
        connection.failure_reason = "authorization_abandoned"
        await ctx.db.flush()
        return None
    return connection


def _scopes_for(institution: Institution) -> list[str] | None:
    scopes = [
        scope for scope in REQUESTED_SCOPES if scope in institution.supported_scopes
    ]
    return scopes if "patient/Observation.read" in scopes else None


def _new_connection(
    ctx: RequestContext,
    institution: Institution,
    scopes: list[str],
    consent_text_version: str,
) -> InstitutionConnection:
    connection = InstitutionConnection(
        patient_user_id=UUID(ctx.user_id),
        institution_id=institution.id,
        origin="auto_public" if institution.type == "public" else "user_added",
        status="authorizing",
        consent_text_version=consent_text_version,
        consented_at=datetime.now(UTC),
        requested_scopes=scopes,
    )
    ctx.db.add(connection)
    return connection


async def _push_authorization(
    client: httpx.AsyncClient,
    institution: Institution,
    scopes: list[str],
    idnp: str,
) -> PushedAuthorization:
    """Send the IDNP server-to-server in a PAR; only the opaque request_uri
    reaches the browser."""
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce()
    pushed = await _post_oauth(
        client,
        _endpoint(institution, "par"),
        institution,
        {
            "client_id": institution.oauth_client_id,
            "redirect_uri": CALLBACK_URL,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "idnp": idnp,
        },
    )
    request_uri = pushed.get("request_uri")
    if not request_uri:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Institution returned an invalid PAR response"
        )
    return PushedAuthorization(
        state=state,
        code_verifier=verifier,
        authorize_url=f"{_endpoint(institution, 'authorize')}?{urlencode({'request_uri': request_uri})}",
    )


async def _save_oauth_state(
    ctx: RequestContext,
    connection: InstitutionConnection,
    pushed: PushedAuthorization,
    next_url: str | None = None,
    batch: bool = False,
) -> None:
    await redis_client.setex(
        f"institution_oauth:{pushed.state}",
        OAUTH_STATE_TTL,
        json.dumps(
            {
                "user_id": ctx.user_id,
                "connection_id": str(connection.id),
                "code_verifier": pushed.code_verifier,
                "next_url": next_url,
                "batch": batch,
            }
        ),
    )


async def _audit_connection(
    ctx: RequestContext,
    connection: InstitutionConnection,
    action: str,
    outcome: str,
) -> None:
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=ctx.user_id,
        action=action,
        resource_type="institution_connection",
        resource_id=connection.id,
        institution_id=connection.institution_id,
        outcome=outcome,
    )


@router.post("/institutions/connect", response_model=ConnectPublicResponse)
async def connect_public_institutions(
    body: ConnectPublicRequest,
    ctx: RequestContext = Depends(get_request_context),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """One consent covers every chosen public institution: start an OAuth
    authorization against each one not already connected, and chain them so
    the callback hands the browser on to the next institution."""
    institutions = (
        await ctx.db.scalars(
            select(Institution)
            .where(Institution.is_active.is_(True), Institution.type == "public")
            .order_by(Institution.name)
        )
    ).all()
    # Ids outside the active public catalogue are simply never matched.
    if body.institution_ids is not None:
        chosen = set(body.institution_ids)
        institutions = [i for i in institutions if i.id in chosen]

    pending: list[tuple[Institution, InstitutionConnection, list[str]]] = []
    for institution in institutions:
        if await _live_connection(ctx, institution.id) is not None:
            continue
        scopes = _scopes_for(institution)
        if scopes is None:
            continue
        connection = _new_connection(
            ctx, institution, scopes, body.consent_text_version
        )
        pending.append((institution, connection, scopes))
    if not pending:
        return ConnectPublicResponse(authorize_url=None, connections=[])
    await ctx.db.flush()

    results = await asyncio.gather(
        *(
            _push_authorization(client, institution, scopes, body.idnp)
            for institution, _, scopes in pending
        ),
        return_exceptions=True,
    )
    started: list[tuple[InstitutionConnection, PushedAuthorization]] = []
    for (_, connection, _), result in zip(pending, results):
        if isinstance(result, HTTPException):
            # One unreachable institution must not block the others.
            connection.status = "error"
            connection.failure_reason = "authorization_request_failed"
            await _audit_connection(ctx, connection, "connection.requested", "failure")
        elif isinstance(result, BaseException):
            raise result
        else:
            started.append((connection, result))
            await _audit_connection(ctx, connection, "connection.requested", "success")

    next_url = None
    for connection, pushed in reversed(started):
        await _save_oauth_state(ctx, connection, pushed, next_url, batch=True)
        next_url = pushed.authorize_url

    return ConnectPublicResponse(
        authorize_url=next_url,
        connections=[
            ConnectionAttempt(
                connection_id=connection.id,
                institution_id=connection.institution_id,
                status=connection.status,
            )
            for _, connection, _ in pending
        ],
    )


@router.post("/institutions/{institution_id}/connect", response_model=ConnectResponse)
async def connect_institution(
    institution_id: UUID,
    body: ConnectRequest,
    ctx: RequestContext = Depends(get_request_context),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    institution = await ctx.db.scalar(
        select(Institution).where(
            Institution.id == institution_id, Institution.is_active.is_(True)
        )
    )
    if institution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution not found")

    if await _live_connection(ctx, institution_id) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Institution already connected or pending"
        )

    scopes = _scopes_for(institution)
    if scopes is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Institution does not support required scopes"
        )

    connection = _new_connection(ctx, institution, scopes, body.consent_text_version)
    await ctx.db.flush()

    pushed = await _push_authorization(client, institution, scopes, body.idnp)
    await _save_oauth_state(ctx, connection, pushed)
    await _audit_connection(ctx, connection, "connection.requested", "success")
    return ConnectResponse(
        connection_id=connection.id, authorize_url=pushed.authorize_url
    )


def _back_to_frontend(result: str) -> RedirectResponse:
    return RedirectResponse(
        f"{FRONTEND_URL}/institutions?{urlencode({'connection': result})}",
        status_code=302,
    )


async def _complete_authorization(
    ctx: RequestContext,
    client: httpx.AsyncClient,
    connection: InstitutionConnection,
    code: str | None,
    error: str | None,
    code_verifier: str,
) -> None:
    if error or not code:
        connection.status = "no_match"
        connection.failure_reason = "access_denied"
        await _audit_connection(ctx, connection, "connection.no_match", "failure")
        return

    try:
        tokens = await _post_oauth(
            client,
            _endpoint(connection.institution, "token"),
            connection.institution,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CALLBACK_URL,
                "code_verifier": code_verifier,
            },
        )
    except HTTPException:
        connection.status = "error"
        connection.failure_reason = "token_exchange_failed"
        await _audit_connection(ctx, connection, "connection.failed", "failure")
        return
    if not tokens.get("access_token") or not tokens.get("patient"):
        connection.status = "error"
        connection.failure_reason = "invalid_token_response"
        await _audit_connection(ctx, connection, "connection.failed", "failure")
        return

    now = datetime.now(UTC)
    connection.status = "active"
    connection.granted_scopes = tokens.get("scope", "").split()
    connection.fhir_patient_ref = tokens["patient"]
    connection.access_token_ciphertext = _encrypt(tokens["access_token"])
    connection.access_token_expires_at = now + timedelta(
        seconds=int(tokens.get("expires_in", 900))
    )
    connection.refresh_token_ciphertext = (
        _encrypt(tokens["refresh_token"]) if tokens.get("refresh_token") else None
    )
    connection.token_key_version = 1
    connection.connected_at = now
    connection.failure_reason = None
    await _audit_connection(ctx, connection, "connection.connected", "success")


@router.get("/institutions/callback")
async def institution_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    # The browser lands here, so failures redirect back to the page with a
    # generic result instead of showing a raw JSON error.
    raw_state = await redis_client.getdel(f"institution_oauth:{state}")
    if not raw_state:
        return _back_to_frontend("expired")
    oauth_state = json.loads(raw_state)
    if oauth_state["user_id"] != ctx.user_id:
        return _back_to_frontend("error")

    connection = await _active_connection(ctx, UUID(oauth_state["connection_id"]))
    if connection.status != "authorizing":
        return _back_to_frontend("error")

    await _complete_authorization(
        ctx, client, connection, code, error, oauth_state["code_verifier"]
    )
    if oauth_state.get("next_url"):
        return RedirectResponse(oauth_state["next_url"], status_code=302)
    if oauth_state.get("batch"):
        return _back_to_frontend("done")
    return _back_to_frontend(connection.status)


async def _access_token(
    connection: InstitutionConnection,
    client: httpx.AsyncClient,
    ctx: RequestContext,
) -> tuple[str, bool]:
    if (
        connection.access_token_expires_at
        and connection.access_token_expires_at
        > datetime.now(UTC) + timedelta(seconds=30)
    ):
        return _decrypt(connection.access_token_ciphertext), False
    if not connection.refresh_token_ciphertext:
        connection.status = "expired"
        await ctx.db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Institution connection expired")

    try:
        tokens = await _post_oauth(
            client,
            _endpoint(connection.institution, "token"),
            connection.institution,
            {
                "grant_type": "refresh_token",
                "refresh_token": _decrypt(connection.refresh_token_ciphertext),
            },
        )
    except HTTPException as error:
        connection.status = "expired"
        await ctx.db.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Institution connection expired"
        ) from error
    if not tokens.get("access_token"):
        connection.status = "expired"
        await ctx.db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Institution connection expired")
    now = datetime.now(UTC)
    connection.access_token_ciphertext = _encrypt(tokens["access_token"])
    connection.access_token_expires_at = now + timedelta(
        seconds=int(tokens.get("expires_in", 900))
    )
    if tokens.get("refresh_token"):
        connection.refresh_token_ciphertext = _encrypt(tokens["refresh_token"])
    return tokens["access_token"], True


@router.get("/institution-connections/{connection_id}/observations")
async def get_observations(
    connection_id: UUID,
    category: str | None = Query(default=None),
    code: str | None = Query(default=None),
    ctx: RequestContext = Depends(get_request_context),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    connection = await _active_connection(ctx, connection_id)
    if connection.status != "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Institution connection is not active"
        )
    access_token, refreshed = await _access_token(connection, client, ctx)
    params = {
        key: value
        for key, value in {"category": category, "code": code}.items()
        if value
    }
    try:
        response = await client.get(
            f"{_endpoint(connection.institution, 'fhir')}/Observation",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        bundle = response.json()
    except (httpx.HTTPError, ValueError) as error:
        if refreshed:
            await ctx.db.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Institution records unavailable"
        ) from error

    connection.last_fetched_at = datetime.now(UTC)
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=ctx.user_id,
        action="institution.fetch",
        resource_type="fhir:Observation",
        resource_id=connection.id,
        institution_id=connection.institution_id,
        outcome="success",
        metadata={"result_count": bundle.get("total", 0)},
    )
    return JSONResponse(bundle, headers={"Cache-Control": "no-store"})


@router.delete("/institution-connections/{connection_id}", status_code=204)
async def revoke_connection(
    connection_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    connection = await _active_connection(ctx, connection_id)
    if connection.status == "revoked":
        return Response(status_code=204)
    token = connection.refresh_token_ciphertext or connection.access_token_ciphertext
    if token:
        try:
            await _post_oauth(
                client,
                _endpoint(connection.institution, "revoke"),
                connection.institution,
                {"token": _decrypt(token)},
            )
        except HTTPException:
            pass

    connection.status = "revoked"
    connection.revoked_at = datetime.now(UTC)
    connection.revoked_by_user_id = UUID(ctx.user_id)
    connection.access_token_ciphertext = None
    connection.access_token_expires_at = None
    connection.refresh_token_ciphertext = None
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=ctx.user_id,
        action="connection.revoked",
        resource_type="institution_connection",
        resource_id=connection.id,
        institution_id=connection.institution_id,
        outcome="success",
    )
    return Response(status_code=204)
