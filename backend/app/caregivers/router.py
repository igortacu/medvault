"""Caregiver access endpoints (Epic 3, Story 1).

Invite / accept / reject and the two directional list views. The relationship is
many-to-many and default-deny: a caregiver has no access until the patient grants
per-category permissions (handled by the permissions endpoints).

Enforcement lives in the database, not here:
  * A patient may only create/list/revoke their *own* links (RLS `links_patient`).
  * A caregiver may only read links where they are the caregiver (`links_caregiver_read`).
  * Accept/reject go through the `caregiver_accept_invite` / `caregiver_reject_invite`
    SECURITY DEFINER functions, which succeed only when the invite's phone matches
    the caller's own verified phone.
This module adds the HTTP surface, input validation and audit around those rules.
"""
import datetime
import json
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.database import redis_client
from app.models.caregiver import CaregiverLink, CaregiverPermission
from app.models.enums import DataCategory

_CATEGORY_VALUES = {c.value for c in DataCategory}

router = APIRouter(prefix="/caregivers", tags=["caregivers"])

_PHONE_RE = re.compile(r"^\+373[0-9]{8}$")


def normalize_phone(raw: str) -> str:
    """Normalise to the stored +373XXXXXXXX form, or raise a 422."""
    cleaned = re.sub(r"[\s\-()]", "", raw or "")
    if not _PHONE_RE.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phone must be a Moldovan number in +373XXXXXXXX format.",
        )
    return cleaned


class InviteRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str

    @field_validator("first_name", "last_name")
    @classmethod
    def _name_length(cls, value: str) -> str:
        trimmed = value.strip()
        if not (2 <= len(trimmed) <= 50):
            raise ValueError("Name must be between 2 and 50 characters.")
        return trimmed


class PermissionItem(BaseModel):
    category: str
    can_view: bool
    can_view_original: bool
    can_export: bool
    can_upload: bool


class CaregiverLinkItem(BaseModel):
    """A person with access (or a pending invite) to the caller's vault."""
    id: UUID
    caregiver_user_id: UUID | None = None
    first_name: str
    last_name: str
    phone: str
    status: str
    invited_at: datetime.datetime | None = None
    responded_at: datetime.datetime | None = None
    permissions: list[PermissionItem] = []


class CaredPatientItem(BaseModel):
    """A patient the caller cares for."""
    link_id: UUID
    patient_user_id: UUID
    status: str
    since: datetime.datetime | None = None
    permissions: list[PermissionItem] = []


class InviteResponse(BaseModel):
    id: UUID
    status: str
    first_name: str
    last_name: str
    phone: str
    invited_at: datetime.datetime | None = None


class LinkActionResponse(BaseModel):
    id: UUID
    status: str


async def _audit(
    ctx: RequestContext,
    *,
    action: str,
    outcome: str,
    subject_patient_id: UUID | None = None,
    resource_id: UUID | None = None,
    extra: dict | None = None,
) -> None:
    metadata = {"outcome": outcome}
    if extra:
        metadata.update(extra)
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=subject_patient_id,
        action=action,
        resource_type="caregiver_link",
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata,
    )


def _permission_items(permissions: list[CaregiverPermission]) -> list[PermissionItem]:
    return [
        PermissionItem(
            category=str(getattr(p.category, "value", p.category)),
            can_view=p.can_view,
            can_view_original=p.can_view_original,
            can_export=p.can_export,
            can_upload=p.can_upload,
        )
        for p in permissions
    ]


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_caregiver(
    body: InviteRequest,
    ctx: RequestContext = Depends(get_request_context),
) -> InviteResponse:
    """Invite a caregiver by name + phone. The link stays 'pending' until accepted."""
    actor = UUID(str(ctx.user_id))
    phone = normalize_phone(body.phone)

    link = CaregiverLink(
        patient_user_id=actor,
        invited_first_name=body.first_name,
        invited_last_name=body.last_name,
        invited_phone_e164=phone,
    )
    ctx.db.add(link)
    try:
        await ctx.db.flush()
    except IntegrityError:
        await ctx.db.rollback()
        await _audit(
            ctx, action="caregiver_invite", outcome="rejected", subject_patient_id=actor
        )
        await ctx.db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is already a live invite or link for this phone number.",
        )

    await _audit(
        ctx,
        action="caregiver_invite",
        outcome="success",
        subject_patient_id=actor,
        resource_id=link.id,
    )
    await ctx.db.commit()

    return InviteResponse(
        id=link.id,
        status="pending",
        first_name=body.first_name,
        last_name=body.last_name,
        phone=phone,
        invited_at=getattr(link, "invited_at", None),
    )


async def _respond_to_invite(
    ctx: RequestContext, link_id: UUID, *, function: str, action: str, new_status: str
) -> LinkActionResponse:
    """Shared body for accept/reject; both wrap a SECURITY DEFINER function that
    verifies the caller owns the invited phone and raises if not."""
    try:
        await ctx.db.scalar(
            text(f"SELECT medvault.{function}(CAST(:id AS uuid))"),
            {"id": str(link_id)},
        )
    except Exception:
        await ctx.db.rollback()
        await _audit(ctx, action=action, outcome="denied", resource_id=link_id)
        await ctx.db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or not addressed to you.",
        )

    await _audit(ctx, action=action, outcome="success", resource_id=link_id)
    await ctx.db.commit()
    return LinkActionResponse(id=link_id, status=new_status)


@router.post("/links/{link_id}/accept", response_model=LinkActionResponse)
async def accept_invite(
    link_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> LinkActionResponse:
    return await _respond_to_invite(
        ctx,
        link_id,
        function="caregiver_accept_invite",
        action="caregiver_accept",
        new_status="active",
    )


@router.post("/links/{link_id}/reject", response_model=LinkActionResponse)
async def reject_invite(
    link_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> LinkActionResponse:
    return await _respond_to_invite(
        ctx,
        link_id,
        function="caregiver_reject_invite",
        action="caregiver_reject",
        new_status="rejected",
    )


async def _permissions_by_link(
    ctx: RequestContext, link_ids: list[UUID]
) -> dict[UUID, list[CaregiverPermission]]:
    if not link_ids:
        return {}
    rows = (
        await ctx.db.execute(
            select(CaregiverPermission).where(CaregiverPermission.link_id.in_(link_ids))
        )
    ).scalars().all()
    grouped: dict[UUID, list[CaregiverPermission]] = {}
    for row in rows:
        grouped.setdefault(row.link_id, []).append(row)
    return grouped


@router.get(
    "",
    response_model=list[CaregiverLinkItem],
    response_model_exclude_none=True,
)
async def list_caregivers(
    ctx: RequestContext = Depends(get_request_context),
) -> list[CaregiverLinkItem]:
    """People with access to me (and pending invites I sent). RLS scopes to own links."""
    actor = UUID(str(ctx.user_id))
    links = (
        await ctx.db.execute(
            select(CaregiverLink)
            .where(CaregiverLink.patient_user_id == actor)
            .order_by(CaregiverLink.invited_at.desc())
        )
    ).scalars().all()

    perms = await _permissions_by_link(ctx, [link.id for link in links])

    items = [
        CaregiverLinkItem(
            id=link.id,
            caregiver_user_id=link.caregiver_user_id,
            first_name=link.invited_first_name,
            last_name=link.invited_last_name,
            phone=link.invited_phone_e164,
            status=str(getattr(link.status, "value", link.status)),
            invited_at=link.invited_at,
            responded_at=link.responded_at,
            permissions=_permission_items(perms.get(link.id, [])),
        )
        for link in links
    ]

    await _audit(
        ctx, action="list_caregivers", outcome="success", subject_patient_id=actor
    )
    await ctx.db.commit()
    return items


@router.get(
    "/patients",
    response_model=list[CaredPatientItem],
    response_model_exclude_none=True,
)
async def list_cared_patients(
    ctx: RequestContext = Depends(get_request_context),
) -> list[CaredPatientItem]:
    """Patients I care for (active links only). RLS scopes to links where I am the caregiver."""
    actor = UUID(str(ctx.user_id))
    links = (
        await ctx.db.execute(
            select(CaregiverLink)
            .where(
                CaregiverLink.caregiver_user_id == actor,
                CaregiverLink.status == "active",
            )
            .order_by(CaregiverLink.responded_at.desc())
        )
    ).scalars().all()

    perms = await _permissions_by_link(ctx, [link.id for link in links])

    items = [
        CaredPatientItem(
            link_id=link.id,
            patient_user_id=link.patient_user_id,
            status=str(getattr(link.status, "value", link.status)),
            since=link.responded_at,
            permissions=_permission_items(perms.get(link.id, [])),
        )
        for link in links
    ]

    await _audit(ctx, action="list_cared_patients", outcome="success")
    await ctx.db.commit()
    return items


# --- Modify permissions -------------------------------------------------------
class PermissionUpdate(BaseModel):
    category: str
    can_view: bool = False
    can_view_original: bool = False
    can_export: bool = False
    can_upload: bool = False

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str) -> str:
        if value not in _CATEGORY_VALUES:
            raise ValueError("Unknown data category.")
        return value

    @field_validator("can_upload")  # runs last; all sibling fields are populated
    @classmethod
    def _actions_imply_view(cls, value: bool, info) -> bool:
        data = info.data
        if (value or data.get("can_view_original") or data.get("can_export")) and not data.get(
            "can_view"
        ):
            raise ValueError("can_view is required when any other action is granted.")
        return value


class PermissionsUpdate(BaseModel):
    permissions: list[PermissionUpdate]


@router.put(
    "/links/{link_id}/permissions",
    response_model=list[PermissionItem],
    response_model_exclude_none=True,
)
async def modify_permissions(
    link_id: UUID,
    body: PermissionsUpdate,
    ctx: RequestContext = Depends(get_request_context),
) -> list[PermissionItem]:
    """Set per-category permissions on a link. Effective immediately; never cached —
    every data request re-reads the grant. RLS (`perms_patient`) additionally ensures
    only the patient who owns the link can write here."""
    actor = UUID(str(ctx.user_id))

    # RLS returns the link only if it belongs to the caller.
    link = await ctx.db.get(CaregiverLink, link_id)
    if link is None:
        await _audit(
            ctx, action="modify_permissions", outcome="denied", resource_id=link_id
        )
        await ctx.db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    existing = (
        await ctx.db.execute(
            select(CaregiverPermission).where(CaregiverPermission.link_id == link_id)
        )
    ).scalars().all()
    by_category = {str(getattr(p.category, "value", p.category)): p for p in existing}

    for entry in body.permissions:
        current = by_category.get(entry.category)
        if current is None:
            current = CaregiverPermission(link_id=link_id, category=entry.category)
            ctx.db.add(current)
            by_category[entry.category] = current
        current.can_view = entry.can_view
        current.can_view_original = entry.can_view_original
        current.can_export = entry.can_export
        current.can_upload = entry.can_upload

    await _audit(
        ctx,
        action="modify_permissions",
        outcome="success",
        subject_patient_id=actor,
        resource_id=link_id,
        extra={"categories": [e.category for e in body.permissions]},
    )
    await ctx.db.commit()

    return _permission_items(list(by_category.values()))


# --- Revoke access ------------------------------------------------------------
@router.post("/links/{link_id}/revoke", response_model=LinkActionResponse)
async def revoke_access(
    link_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> LinkActionResponse:
    """Patient-side revocation. Sets the link to 'revoked' (with revoked_at/by to
    satisfy the consistency CHECK); caregiver_can then returns false immediately."""
    actor = UUID(str(ctx.user_id))

    link = await ctx.db.get(CaregiverLink, link_id)
    if link is None or str(getattr(link.status, "value", link.status)) not in (
        "pending",
        "active",
    ):
        await _audit(ctx, action="revoke_access", outcome="denied", resource_id=link_id)
        await ctx.db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found or already ended.",
        )

    link.status = "revoked"
    link.revoked_at = datetime.datetime.now(datetime.timezone.utc)
    link.revoked_by_user_id = actor

    await _audit(
        ctx,
        action="revoke_access",
        outcome="success",
        subject_patient_id=actor,
        resource_id=link_id,
    )
    await ctx.db.commit()
    return LinkActionResponse(id=link_id, status="revoked")


# --- Vault switching ----------------------------------------------------------
class VaultSwitchRequest(BaseModel):
    # None switches back to the caller's own vault.
    patient_id: UUID | None = None


class VaultResponse(BaseModel):
    acting_patient_id: UUID | None = None


async def _store_acting_patient(session_id: str, user_id: str, acting: str | None) -> None:
    """Persist the vault selection into the Redis session, preserving its TTL."""
    key = f"session:{session_id}"
    raw = await redis_client.get(key)
    data: dict = {}
    if raw:
        try:
            data = json.loads(raw) if raw.startswith("{") else {"user_id": raw}
        except (json.JSONDecodeError, AttributeError):
            data = {"user_id": raw}
    data["user_id"] = user_id
    if acting:
        data["acting_patient_id"] = acting
    else:
        data.pop("acting_patient_id", None)
    ttl = await redis_client.ttl(key)
    await redis_client.set(key, json.dumps(data), ex=ttl if ttl and ttl > 0 else None)


@router.get("/vault", response_model=VaultResponse)
async def current_vault(
    ctx: RequestContext = Depends(get_request_context),
) -> VaultResponse:
    acting = ctx.acting_patient_id
    return VaultResponse(acting_patient_id=UUID(acting) if acting else None)


@router.post("/vault/switch", response_model=VaultResponse)
async def switch_vault(
    body: VaultSwitchRequest,
    ctx: RequestContext = Depends(get_request_context),
) -> VaultResponse:
    """Select which vault the caregiver is acting in. Verifies an active link exists;
    the selection is stored in the session, not the effective permissions."""
    actor = UUID(str(ctx.user_id))
    acting: str | None = None

    if body.patient_id and body.patient_id != actor:
        active = await ctx.db.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM medvault.caregiver_links "
                "WHERE patient_user_id = CAST(:p AS uuid) "
                "AND caregiver_user_id = CAST(:a AS uuid) AND status = 'active')"
            ),
            {"p": str(body.patient_id), "a": str(actor)},
        )
        if not active:
            await _audit(
                ctx,
                action="vault_switch",
                outcome="denied",
                subject_patient_id=body.patient_id,
            )
            await ctx.db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have an active caregiver link for that patient.",
            )
        acting = str(body.patient_id)

    if ctx.session_id:
        await _store_acting_patient(ctx.session_id, str(actor), acting)

    await _audit(
        ctx,
        action="vault_switch",
        outcome="success",
        subject_patient_id=body.patient_id if acting else actor,
    )
    await ctx.db.commit()
    return VaultResponse(acting_patient_id=UUID(acting) if acting else None)
