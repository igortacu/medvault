"""Live original files for institutional records (Epic 2, story 10).

An institutional record's original (a scanned certificate, a discharge summary PDF)
stays at the institution. When the patient, or a caregiver allowed `view_original`,
opens it, this re-reads the record live, follows its attachment to the institution's
`Binary` endpoint and hands the bytes back to stream to the browser. Nothing is
written to disk, MinIO or the database apart from token refreshes, which go through
the same locked path as the aggregation layer.
"""
import re
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy import select, text

from app.aggregation import client, mapping, service
from app.models.institution import Institution

institutions = service.institutions

# institution:<external_id>/<ResourceType>/<id>, as built by mapping.record_reference.
REFERENCE = re.compile(
    r"^institution:(?P<external_id>[a-z0-9-]{1,64})/"
    r"(?P<resource_type>[A-Za-z]{1,40})/(?P<resource_id>[A-Za-z0-9.\-]{1,64})$"
)
ALLOWED_CONTENT_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})
MAX_ORIGINAL_BYTES = 20 * 1024 * 1024
FILE_TIMEOUT = httpx.Timeout(15.0, connect=4.0)


class OriginalError(Exception):
    """Why the original can't be served. `reason` is one of:
    forbidden, not_found, reconnect, unreachable."""

    def __init__(self, reason: str, *, institution_id: UUID | None = None):
        super().__init__(reason)
        self.reason = reason
        self.institution_id = institution_id


@dataclass
class Original:
    content: bytes
    content_type: str
    institution_id: UUID


def parse_reference(reference: str) -> tuple[str, str, str] | None:
    match = REFERENCE.match(reference or "")
    if not match:
        return None
    return match["external_id"], match["resource_type"], match["resource_id"]


def _binary_url(url: str, fhir_base: str) -> str | None:
    """The attachment URL as an absolute Binary URL under the institution's FHIR base,
    or None. Institution-controlled data, so anything else is refused (no SSRF)."""
    absolute = url if url.startswith(("http://", "https://")) else f"{fhir_base}/{url}"
    if not client._same_origin_under(absolute, fhir_base):
        return None
    if "/Binary/" not in httpx.URL(absolute).path:
        return None
    return absolute


async def _read_resource(http, fhir_base: str, token: str, rtype: str, rid: str) -> dict:
    try:
        bundle = await client._get(http, f"{fhir_base}/{rtype}", token, {"_id": rid})
    except client.SourceFailure as failure:
        raise OriginalError("reconnect" if failure.status == "unauthorised" else "unreachable")
    for entry in bundle.get("entry", []):
        resource = entry.get("resource")
        if isinstance(resource, dict) and str(resource.get("id")) == rid:
            return resource
    raise OriginalError("not_found")


async def _read_file(http, url: str, token: str) -> tuple[bytes, str]:
    try:
        response = await http.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": ", ".join(sorted(ALLOWED_CONTENT_TYPES)),
            },
            timeout=FILE_TIMEOUT,
        )
    except httpx.HTTPError:
        raise OriginalError("unreachable")
    if response.status_code in (401, 403):
        raise OriginalError("reconnect")
    if response.status_code == 404:
        raise OriginalError("not_found")
    if response.status_code >= 400:
        raise OriginalError("unreachable")
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise OriginalError("unreachable")
    if len(response.content) > MAX_ORIGINAL_BYTES:
        raise OriginalError("unreachable")
    return response.content, content_type


async def fetch_original(
    ctx,
    reference: str,
    category: str,
    patient_id: UUID,
    http: httpx.AsyncClient | None = None,
) -> Original:
    parsed = parse_reference(reference)
    if parsed is None:
        raise OriginalError("not_found")
    external_id, rtype, rid = parsed
    if rtype not in mapping.CATEGORY_RESOURCE_TYPES.get(category, ()):
        raise OriginalError("not_found")

    is_owner = UUID(str(ctx.user_id)) == patient_id
    if not is_owner:
        # Opening an original is its own permission, stricter than seeing the list.
        allowed = await ctx.db.scalar(
            text(
                "SELECT medvault.caregiver_can(CAST(:p AS uuid), "
                "CAST(:c AS medvault.data_category), 'view_original')"
            ),
            {"p": str(patient_id), "c": category},
        )
        if not allowed:
            raise OriginalError("forbidden")

    institution = await ctx.db.scalar(
        select(Institution).where(Institution.external_id == external_id)
    )
    if institution is None:
        raise OriginalError("not_found")
    rows = (
        await ctx.db.execute(
            text(
                "SELECT * FROM medvault.caregiver_visible_connections("
                "CAST(:p AS uuid), CAST(:c AS medvault.data_category))"
            ),
            {"p": str(patient_id), "c": category},
        )
    ).all()
    row = next((r for r in rows if r.institution_id == institution.id), None)
    # Not connected (or disconnected): the record is no longer reachable at all.
    if row is None or mapping.scope_for(rtype) not in set(row.granted_scopes or []):
        raise OriginalError("not_found", institution_id=institution.id)

    owned_http = http is None
    http = http or httpx.AsyncClient(timeout=client.TIMEOUT, follow_redirects=False)
    try:
        try:
            token = await service._token(ctx, row, institution, http, is_owner)
        except client.SourceFailure as failure:
            reason = "reconnect" if failure.status == "unauthorised" else "unreachable"
            raise OriginalError(reason, institution_id=institution.id)
        # Don't hold a pooled DB connection while the institution answers.
        await service._release(ctx)

        fhir_base = institutions._endpoint(institution, "fhir")
        try:
            resource = await _read_resource(http, fhir_base, token, rtype, rid)
            # The caregiver gate was checked for `category`, so the record must really
            # be one of its rows: a sick note can't be opened by naming another page.
            row_for_category = mapping.normalize(
                category,
                resource,
                external_id=external_id,
                institution_name=institution.name,
            )
            if row_for_category is None:
                raise OriginalError("not_found")
            url = mapping.attachment_url(resource)
            binary = _binary_url(url, fhir_base) if url else None
            if binary is None:
                raise OriginalError("not_found")
            content, content_type = await _read_file(http, binary, token)
        except OriginalError as error:
            error.institution_id = institution.id
            raise
        return Original(content, content_type, institution.id)
    finally:
        if owned_http:
            await http.aclose()
