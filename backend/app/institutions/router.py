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
OAUTH_STATE_TTL = 120
REQUESTED_SCOPES = (
    "patient/Patient.read",
    "patient/Observation.read",
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
    connected_at: datetime | None
    revoked_at: datetime | None


class ConnectRequest(BaseModel):
    idnp: str = Field(pattern=r"^[0-9]{13}$")
    consent_text_version: str = Field(min_length=1, max_length=50)


class ConnectResponse(BaseModel):
    connection_id: UUID
    authorize_url: str


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        yield client


def _endpoint(institution: Institution, endpoint: str) -> str:
    if MOCK_BASE_URL:
        suffix = "fhir" if endpoint == "fhir" else f"oauth/{endpoint}"
        return f"{MOCK_BASE_URL}/{institution.external_id}/{suffix}"
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

    existing = await ctx.db.scalar(
        select(InstitutionConnection).where(
            InstitutionConnection.institution_id == institution_id,
            InstitutionConnection.status.in_(
                ("pending_consent", "authorizing", "active")
            ),
        )
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Institution already connected or pending"
        )

    scopes = [
        scope for scope in REQUESTED_SCOPES if scope in institution.supported_scopes
    ]
    if "patient/Observation.read" not in scopes:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Institution does not support required scopes"
        )

    connection = InstitutionConnection(
        patient_user_id=UUID(ctx.user_id),
        institution_id=institution.id,
        origin="user_added",
        status="authorizing",
        consent_text_version=body.consent_text_version,
        consented_at=datetime.now(UTC),
        requested_scopes=scopes,
    )
    ctx.db.add(connection)
    await ctx.db.flush()

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
            "idnp": body.idnp,
        },
    )
    request_uri = pushed.get("request_uri")
    if not request_uri:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Institution returned an invalid PAR response"
        )

    await redis_client.setex(
        f"institution_oauth:{state}",
        OAUTH_STATE_TTL,
        json.dumps(
            {
                "user_id": ctx.user_id,
                "connection_id": str(connection.id),
                "code_verifier": verifier,
            }
        ),
    )
    authorize_url = f"{_endpoint(institution, 'authorize')}?{urlencode({'request_uri': request_uri})}"
    return ConnectResponse(connection_id=connection.id, authorize_url=authorize_url)


@router.get("/institutions/callback")
async def institution_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    raw_state = await redis_client.getdel(f"institution_oauth:{state}")
    if not raw_state:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired OAuth state"
        )
    oauth_state = json.loads(raw_state)
    if oauth_state["user_id"] != ctx.user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "OAuth state does not belong to this session"
        )

    connection = await _active_connection(ctx, UUID(oauth_state["connection_id"]))
    if connection.status != "authorizing":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Connection is not awaiting authorization"
        )
    if error or not code:
        connection.status = "no_match"
        connection.failure_reason = "access_denied"
        return RedirectResponse(
            f"{FRONTEND_URL}/institutions?connection=no_match", status_code=302
        )

    try:
        tokens = await _post_oauth(
            client,
            _endpoint(connection.institution, "token"),
            connection.institution,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CALLBACK_URL,
                "code_verifier": oauth_state["code_verifier"],
            },
        )
    except HTTPException:
        connection.status = "error"
        connection.failure_reason = "token_exchange_failed"
        await ctx.db.commit()
        raise
    if not tokens.get("access_token") or not tokens.get("patient"):
        connection.status = "error"
        connection.failure_reason = "invalid_token_response"
        await ctx.db.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Institution returned an invalid token response",
        )

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
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=ctx.user_id,
        action="connection.connected",
        resource_type="institution_connection",
        resource_id=connection.id,
        institution_id=connection.institution_id,
        outcome="success",
    )
    return RedirectResponse(
        f"{FRONTEND_URL}/institutions?connection=active", status_code=302
    )


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
