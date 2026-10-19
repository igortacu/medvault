from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response

FIXTURES = Path(__file__).with_name("fixtures")
REDIRECT_URI = os.getenv(
    "INSTITUTION_MOCK_REDIRECT_URI",
    "http://localhost:8000/api/v1/institutions/callback",
)
CLIENT_SECRET = os.getenv(
    "INSTITUTION_MOCK_CLIENT_SECRET",
    "DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD",
)
JWT_SECRET = os.getenv("INSTITUTION_MOCK_JWT_SECRET", "dev-only-jwt-secret-change-me")
ISSUER_BASE = os.getenv("INSTITUTION_MOCK_ISSUER", "http://institution-mock:8001")
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=90)
PAR_TTL = timedelta(seconds=90)
CODE_TTL = timedelta(seconds=60)

# Resource types served from optional fixture files (<Type>.json next to Patient.json).
OPTIONAL_RESOURCE_TYPES = (
    "Condition", "DocumentReference", "MedicationRequest", "MedicationStatement",
    "CarePlan", "Procedure", "DiagnosticReport", "ImagingStudy", "Encounter",
    "Immunization",
)

# Fault injection for exercising the backend's resilience paths, e.g.
# INSTITUTION_MOCK_FAULTS="medpark=slow:15,imsp-scm-balti=500". `slow:N` sleeps N seconds
# before answering; a status code answers every resource search with that error.
FAULTS = dict(
    pair.split("=", 1)
    for pair in os.getenv("INSTITUTION_MOCK_FAULTS", "").split(",")
    if "=" in pair
)

ALLOWED_SCOPES = {
    "patient/Patient.read",
    "patient/Observation.read",
    *(f"patient/{t}.read" for t in OPTIONAL_RESOURCE_TYPES),
    "offline_access",
    "openid",
    "fhirUser",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _jwt_encode(claims: dict[str, Any]) -> str:
    header = _b64(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = hmac.new(
        JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def _jwt_decode(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(
            JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            raise ValueError
        claims = json.loads(_unb64(payload))
        if (
            claims["exp"] <= int(_now().timestamp())
            or claims["aud"] != "medvault"
            or claims["iss"] != f"{ISSUER_BASE}/{claims['institution_id']}"
        ):
            raise ValueError
        return claims
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")


def _security_context(
    collections: dict[str, list[dict[str, Any]]], binary: dict[str, Any]
) -> dict[str, Any] | None:
    """The resource a Binary belongs to; access to the file follows access to it."""
    rtype, _, rid = binary.get("securityContext", {}).get("reference", "").partition("/")
    if rtype not in OPTIONAL_RESOURCE_TYPES:
        return None
    return next((item for item in collections.get(rtype, []) if item["id"] == rid), None)


def _subject(resource: dict[str, Any]) -> str | None:
    return (resource.get("subject") or resource.get("patient") or {}).get("reference")


def _load_fixtures() -> dict[str, dict[str, list[dict[str, Any]]]]:
    loaded: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for directory in sorted(path for path in FIXTURES.iterdir() if path.is_dir()):
        collections = {
            name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("Institution", "Patient", "Observation")
        }
        for name in OPTIONAL_RESOURCE_TYPES:
            optional = directory / f"{name}.json"
            if optional.exists():
                collections[name] = json.loads(optional.read_text(encoding="utf-8"))
        institution = collections["Institution"][0]
        institution_id = institution["id"]
        source = f"urn:medvault:institution:{institution_id}"
        if (
            institution_id != directory.name
            or institution["fhirBasePath"] != f"/{institution_id}/fhir"
        ):
            raise RuntimeError(f"Invalid institution fixture: {directory}")

        patients = {patient["id"] for patient in collections["Patient"]}
        idnps = []
        for patient in collections["Patient"]:
            idnp = next(
                item["value"]
                for item in patient["identifier"]
                if item["system"] == "urn:medvault:idnp"
            )
            idnps.append(idnp)
            if (
                patient["meta"]["source"] != source
                or len(idnp) != 13
                or not idnp.isdigit()
            ):
                raise RuntimeError(f"Invalid patient fixture: {patient.get('id')}")
        if len(idnps) != len(set(idnps)):
            raise RuntimeError(f"Duplicate IDNP in {institution_id}")

        for observation in collections["Observation"]:
            patient_id = observation["subject"]["reference"].removeprefix("Patient/")
            if observation["meta"]["source"] != source or patient_id not in patients:
                raise RuntimeError(
                    f"Invalid observation fixture: {observation.get('id')}"
                )
        for name in OPTIONAL_RESOURCE_TYPES:
            for resource in collections.get(name, []):
                ref = (resource.get("subject") or resource.get("patient") or {}).get(
                    "reference", ""
                )
                if (
                    resource["resourceType"] != name
                    or resource["meta"]["source"] != source
                    or ref.removeprefix("Patient/") not in patients
                ):
                    raise RuntimeError(f"Invalid {name} fixture: {resource.get('id')}")
        observations = {item["id"]: item for item in collections["Observation"]}
        for report in collections.get("DiagnosticReport", []):
            for result in report.get("result", []):
                observation = observations.get(result["reference"].removeprefix("Observation/"))
                if observation is None or observation["subject"] != report["subject"]:
                    raise RuntimeError(f"Invalid DiagnosticReport result: {report['id']}")
        binaries = directory / "Binary.json"
        collections["Binary"] = (
            json.loads(binaries.read_text(encoding="utf-8")) if binaries.exists() else []
        )
        for binary in collections["Binary"]:
            if (
                binary["resourceType"] != "Binary"
                or binary["meta"]["source"] != source
                or _security_context(collections, binary) is None
                or not (directory / "Binary" / f"{binary['id']}.pdf").is_file()
            ):
                raise RuntimeError(f"Invalid Binary fixture: {binary.get('id')}")
        loaded[institution_id] = collections
    if not loaded:
        raise RuntimeError("No institution fixtures found")
    return loaded


FIXTURE_DATA = _load_fixtures()


def _load_planted() -> set[tuple[str, str]]:
    """(institution, patient ref) pairs whose consent the institution revokes after the
    first successful read: the planted "revoked token" case (see README)."""
    path = FIXTURES / "planted.json"
    planted = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    pairs = {(item["institution"], item["patient"]) for item in planted.get("revokedConsent", [])}
    for institution_id, patient_ref in pairs:
        if not any(
            f"Patient/{patient['id']}" == patient_ref
            for patient in FIXTURE_DATA.get(institution_id, {}).get("Patient", [])
        ):
            raise RuntimeError(f"Invalid planted revocation: {institution_id}")
    return pairs


REVOKED_AFTER_FIRST_READ = _load_planted()
RUNTIME: dict[str, dict[str, dict[str, Any]]] = {
    "par": {},
    "codes": {},
    "access": {},
    "refresh": {},
}
ACCESS_LOG: list[dict[str, Any]] = []
RUNTIME_LOCK = asyncio.Lock()

app = FastAPI(title="MedVault Institution Mock", version="0.1.0")


async def _body(request: Request) -> dict[str, str]:
    raw = await request.body()
    if request.headers.get("content-type", "").startswith("application/json"):
        return {key: str(value) for key, value in json.loads(raw or b"{}").items()}
    return {key: values[-1] for key, values in parse_qs(raw.decode()).items()}


def _authenticate_client(
    request: Request, form: dict[str, str], institution_id: str
) -> str:
    client_id = form.get("client_id", "")
    secret = form.get("client_secret", "")
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Basic "):
        try:
            client_id, secret = _unb64(authorization[6:]).decode().split(":", 1)
        except (ValueError, UnicodeDecodeError):
            pass
    expected_id = f"medvault-{institution_id}"
    if client_id != expected_id or not hmac.compare_digest(secret, CLIENT_SECRET):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    return client_id


def _institution(institution_id: str) -> dict[str, list[dict[str, Any]]]:
    fixture = FIXTURE_DATA.get(institution_id)
    if fixture is None or not fixture["Institution"][0]["active"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "institution_not_found")
    return fixture


def _patient_for_idnp(
    fixture: dict[str, list[dict[str, Any]]], idnp: str
) -> str | None:
    for patient in fixture["Patient"]:
        if any(
            item["system"] == "urn:medvault:idnp"
            and hmac.compare_digest(item["value"], idnp)
            for item in patient["identifier"]
        ):
            return f"Patient/{patient['id']}"
    return None


def _redirect(uri: str, **params: str) -> RedirectResponse:
    separator = "&" if "?" in uri else "?"
    return RedirectResponse(f"{uri}{separator}{urlencode(params)}", status_code=302)


@app.post("/{institution_id}/oauth/par")
async def pushed_authorization_request(
    institution_id: str, request: Request
) -> JSONResponse:
    fixture = _institution(institution_id)
    form = await _body(request)
    client_id = _authenticate_client(request, form, institution_id)
    scopes = set(form.get("scope", "").split())
    if (
        form.get("redirect_uri") != REDIRECT_URI
        or not scopes
        or not scopes <= ALLOWED_SCOPES
        or form.get("code_challenge_method") != "S256"
        or not form.get("code_challenge")
        or not form.get("state")
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_request")
    idnp = form.get("idnp", "")
    if len(idnp) != 13 or not idnp.isdigit():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_request")

    raw_request_uri = f"urn:ietf:params:oauth:request_uri:{secrets.token_urlsafe(24)}"
    expires_at = _now() + PAR_TTL
    RUNTIME["par"][_hash(raw_request_uri)] = {
        "client_id": client_id,
        "institution_id": institution_id,
        "patient_ref": _patient_for_idnp(fixture, idnp),
        "scopes": sorted(scopes),
        "redirect_uri": REDIRECT_URI,
        "state": form["state"],
        "code_challenge": form["code_challenge"],
        "expires_at": expires_at,
    }
    return JSONResponse(
        {"request_uri": raw_request_uri, "expires_in": int(PAR_TTL.total_seconds())},
        headers={"Cache-Control": "no-store"},
    )


@app.get("/{institution_id}/oauth/authorize")
async def authorize(institution_id: str, request_uri: str) -> RedirectResponse:
    _institution(institution_id)
    async with RUNTIME_LOCK:
        pushed = RUNTIME["par"].pop(_hash(request_uri), None)
    if (
        pushed is None
        or pushed["expires_at"] <= _now()
        or pushed["institution_id"] != institution_id
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_request_uri")
    if pushed["patient_ref"] is None:
        return _redirect(
            pushed["redirect_uri"], error="access_denied", state=pushed["state"]
        )

    code = secrets.token_urlsafe(32)
    RUNTIME["codes"][_hash(code)] = {**pushed, "expires_at": _now() + CODE_TTL}
    return _redirect(pushed["redirect_uri"], code=code, state=pushed["state"])


def _mint_tokens(record: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    jti = secrets.token_hex(16)
    claims = {
        "iss": f"{ISSUER_BASE}/{record['institution_id']}",
        "aud": "medvault",
        "sub": record["patient_ref"],
        "patient": record["patient_ref"],
        "client_id": record["client_id"],
        "institution_id": record["institution_id"],
        "scope": " ".join(record["scopes"]),
        "iat": int(now.timestamp()),
        "exp": int((now + ACCESS_TOKEN_TTL).timestamp()),
        "jti": jti,
    }
    access_token = _jwt_encode(claims)
    RUNTIME["access"][jti] = {
        **record,
        "expires_at": now + ACCESS_TOKEN_TTL,
        "revoked_at": None,
    }
    response: dict[str, Any] = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "scope": claims["scope"],
        "patient": record["patient_ref"],
    }
    if "offline_access" in record["scopes"]:
        refresh_token = secrets.token_urlsafe(48)
        RUNTIME["refresh"][_hash(refresh_token)] = {
            **record,
            "expires_at": now + REFRESH_TOKEN_TTL,
            "revoked_at": None,
        }
        response["refresh_token"] = refresh_token
    return response


@app.post("/{institution_id}/oauth/token")
async def token(institution_id: str, request: Request) -> JSONResponse:
    _institution(institution_id)
    form = await _body(request)
    client_id = _authenticate_client(request, form, institution_id)
    grant_type = form.get("grant_type")
    if grant_type == "authorization_code":
        async with RUNTIME_LOCK:
            record = RUNTIME["codes"].pop(_hash(form.get("code", "")), None)
        verifier = form.get("code_verifier", "")
        challenge = _b64(hashlib.sha256(verifier.encode()).digest())
        if (
            record is None
            or record["expires_at"] <= _now()
            or record["client_id"] != client_id
            or record["institution_id"] != institution_id
            or record["redirect_uri"] != form.get("redirect_uri")
            or not hmac.compare_digest(record["code_challenge"], challenge)
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")
    elif grant_type == "refresh_token":
        refresh_hash = _hash(form.get("refresh_token", ""))
        async with RUNTIME_LOCK:
            record = RUNTIME["refresh"].pop(refresh_hash, None)
        if (
            record is None
            or record["expires_at"] <= _now()
            or record["revoked_at"] is not None
            or record["client_id"] != client_id
            or record["institution_id"] != institution_id
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported_grant_type")
    return JSONResponse(_mint_tokens(record), headers={"Cache-Control": "no-store"})


@app.post("/{institution_id}/oauth/revoke", status_code=204, response_class=Response)
async def revoke(institution_id: str, request: Request) -> Response:
    _institution(institution_id)
    form = await _body(request)
    client_id = _authenticate_client(request, form, institution_id)
    raw_token = form.get("token", "")
    refresh = RUNTIME["refresh"].get(_hash(raw_token))
    claims: dict[str, Any] | None = None
    if refresh is not None:
        patient_ref = refresh["patient_ref"]
    else:
        try:
            claims = _jwt_decode(raw_token)
            patient_ref = claims["patient"]
        except HTTPException:
            return Response(status_code=204)
    _revoke_grants(client_id, institution_id, patient_ref)
    return Response(status_code=204)


def _revoke_grants(client_id: str, institution_id: str, patient_ref: str) -> None:
    now = _now()
    for collection in (RUNTIME["access"], RUNTIME["refresh"]):
        for record in collection.values():
            if (
                record["client_id"] == client_id
                and record["institution_id"] == institution_id
                and record["patient_ref"] == patient_ref
            ):
                record["revoked_at"] = now


def _bearer(
    request: Request, institution_id: str, required_scope: str
) -> dict[str, Any]:
    claims = _token_claims(request, institution_id)
    _require_scope(request, claims, required_scope)
    return claims


def _require_scope(request: Request, claims: dict[str, Any], required_scope: str) -> None:
    if required_scope not in claims["scope"].split():
        _log(request, claims, 403, 0, "insufficient_scope")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_scope")


def _token_claims(request: Request, institution_id: str) -> dict[str, Any]:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    claims = _jwt_decode(authorization[7:])
    record = RUNTIME["access"].get(claims["jti"])
    if (
        record is None
        or record["revoked_at"] is not None
        or claims["institution_id"] != institution_id
    ):
        _log(request, claims, 401, 0, "invalid_token")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return claims


def _log(
    request: Request,
    claims: dict[str, Any],
    status_code: int,
    result_count: int,
    error_code: str | None = None,
) -> None:
    ACCESS_LOG.append(
        {
            "occurredAt": _now().isoformat(),
            "endpoint": request.url.path,
            "clientId": claims["client_id"],
            "institutionId": claims["institution_id"],
            "patientRef": claims["patient"],
            "tokenJti": claims["jti"],
            "scopes": claims["scope"].split(),
            "httpStatus": status_code,
            "resultCount": result_count,
            "errorCode": error_code,
        }
    )


@app.get("/{institution_id}/fhir/Patient/{patient_id}")
async def get_patient(
    institution_id: str, patient_id: str, request: Request
) -> JSONResponse:
    fixture = _institution(institution_id)
    claims = _bearer(request, institution_id, "patient/Patient.read")
    if claims["patient"] != f"Patient/{patient_id}":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    patient = next(
        (item for item in fixture["Patient"] if item["id"] == patient_id), None
    )
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _served(request, claims, 1)
    return JSONResponse(patient, headers={"Cache-Control": "no-store"})


# Search parameters (FHIR R4 semantics, the subset the backend pages use). Unknown
# parameters are ignored, as a lenient FHIR server does; the subject never comes from
# the query string.
SUBJECT_PARAMS = ("patient", "subject")
TOKEN_FIELDS = {
    "category": ("category",),
    "type": ("type",),
    "code": ("code", "medicationCodeableConcept", "vaccineCode"),
    "class": ("class",),
}
DATE_FIELDS = (
    "effectiveDateTime", "recordedDate", "authoredOn", "date", "performedDateTime",
    "occurrenceDateTime", "started", "created", "issued", "dateAsserted",
)
MAX_COUNT = 100


def _resource_date(resource: dict[str, Any]) -> str | None:
    for name in DATE_FIELDS:
        if isinstance(resource.get(name), str):
            return resource[name][:10]
    return (resource.get("period") or {}).get("start", "")[:10] or None


def _codings(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [coding for item in value for coding in _codings(item)]
    if isinstance(value, dict):
        return value["coding"] if "coding" in value else [value]  # Coding (Encounter.class)
    return []


def _token_match(resource: dict[str, Any], fields: tuple[str, ...], tokens: str) -> bool:
    codings = [c for name in fields for c in _codings(resource.get(name))]
    for token in tokens.split(","):
        system, bar, code = token.rpartition("|")
        if any(
            c.get("code") == code and (not bar or c.get("system") == system)
            for c in codings
        ):
            return True
    return False


def _date_match(value: str | None, expression: str) -> bool:
    prefix, target = (
        (expression[:2], expression[2:]) if expression[:2].isalpha() else ("eq", expression)
    )
    if value is None or not target:
        return False
    head = value[: len(target)]
    return {
        "eq": head == target,
        "ne": head != target,
        "gt": head > target,
        "lt": head < target,
        "ge": head >= target,
        "le": head <= target,
    }.get(prefix, False)


def _reject_subject_param(request: Request, claims: dict[str, Any]) -> None:
    if any(name in request.query_params for name in SUBJECT_PARAMS):
        _log(request, claims, 400, 0, "patient_parameter_rejected")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "the 'patient' query parameter is not accepted; subject comes from the access token",
        )


async def _apply_fault(request: Request, claims: dict[str, Any], institution_id: str) -> None:
    fault = FAULTS.get(institution_id, "")
    if fault.startswith("slow:"):
        try:
            await asyncio.sleep(float(fault.split(":", 1)[1]))
        except ValueError:
            pass  # malformed fault spec: behave normally
    elif fault.isdigit() and 400 <= int(fault) <= 599:
        _log(request, claims, int(fault), 0, "injected_fault")
        raise HTTPException(int(fault), "injected_fault")


def _served(request: Request, claims: dict[str, Any], result_count: int) -> None:
    """Log a successful read; then apply the planted institution-side revocation."""
    _log(request, claims, 200, result_count)
    if (claims["institution_id"], claims["patient"]) in REVOKED_AFTER_FIRST_READ:
        _revoke_grants(claims["client_id"], claims["institution_id"], claims["patient"])


def _int_param(request: Request, name: str) -> int | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid {name}")


def _search(
    fixture: dict[str, list[dict[str, Any]]],
    resource_type: str,
    claims: dict[str, Any],
    request: Request,
) -> JSONResponse:
    params = request.query_params
    matches = [
        item for item in fixture.get(resource_type, []) if _subject(item) == claims["patient"]
    ]
    for name, fields in TOKEN_FIELDS.items():
        for tokens in params.getlist(name):
            matches = [item for item in matches if _token_match(item, fields, tokens)]
    for statuses in params.getlist("status"):
        matches = [item for item in matches if item.get("status") in statuses.split(",")]
    for ids in params.getlist("_id"):
        matches = [item for item in matches if item["id"] in ids.split(",")]
    for expression in params.getlist("date"):
        matches = [
            item for item in matches if _date_match(_resource_date(item), expression)
        ]

    count = _int_param(request, "_count")
    offset = max(0, _int_param(request, "_offset") or 0)
    if count is not None:
        count = min(max(count, 1), MAX_COUNT)
    page = matches[offset : offset + count] if count is not None else matches[offset:]

    entries = [
        {"fullUrl": f"{resource_type}/{item['id']}", "resource": item, "search": {"mode": "match"}}
        for item in page
    ]
    if (
        resource_type == "DiagnosticReport"
        and "DiagnosticReport:result" in params.getlist("_include")
        and "patient/Observation.read" in claims["scope"].split()
    ):
        observations = {item["id"]: item for item in fixture["Observation"]}
        for report in page:
            for result in report.get("result", []):
                included = observations.get(result["reference"].removeprefix("Observation/"))
                if included is not None and _subject(included) == claims["patient"]:
                    entries.append({
                        "fullUrl": f"Observation/{included['id']}",
                        "resource": included,
                        "search": {"mode": "include"},
                    })

    links = [{"relation": "self", "url": str(request.url)}]
    if count is not None and offset + count < len(matches):
        query = [(k, v) for k, v in params.multi_items() if k != "_offset"]
        query.append(("_offset", str(offset + count)))
        links.append(
            {"relation": "next", "url": str(request.url.replace(query=urlencode(query)))}
        )
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(matches),
        "link": links,
        "entry": entries,
    }
    _served(request, claims, len(page))
    return JSONResponse(bundle, headers={"Cache-Control": "no-store"})


@app.get("/{institution_id}/fhir/Observation")
async def get_observations(institution_id: str, request: Request) -> JSONResponse:
    fixture = _institution(institution_id)
    claims = _bearer(request, institution_id, "patient/Observation.read")
    _reject_subject_param(request, claims)
    return _search(fixture, "Observation", claims, request)


@app.get("/{institution_id}/fhir/Binary/{binary_id}")
async def get_binary(institution_id: str, binary_id: str, request: Request) -> Response:
    """A document file, served only if the resource it belongs to (its securityContext)
    is the token's patient's and the token may read that resource type."""
    fixture = _institution(institution_id)
    claims = _token_claims(request, institution_id)
    _reject_subject_param(request, claims)
    binary = next((item for item in fixture["Binary"] if item["id"] == binary_id), None)
    owner = _security_context(fixture, binary) if binary else None
    if owner is None or _subject(owner) != claims["patient"]:
        # Same answer whether the file is missing or someone else's: no existence oracle.
        _log(request, claims, 404, 0, "not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _require_scope(request, claims, f"patient/{owner['resourceType']}.read")
    await _apply_fault(request, claims, institution_id)
    content = (FIXTURES / institution_id / "Binary" / f"{binary_id}.pdf").read_bytes()
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    _served(request, claims, 1)
    if "application/fhir+json" in request.headers.get("accept", ""):
        return JSONResponse(
            {**binary, "data": base64.b64encode(content).decode()},
            media_type="application/fhir+json",
            headers=headers,
        )
    return Response(
        content,
        media_type=binary["contentType"],
        headers={**headers, "Content-Disposition": f'inline; filename="{binary_id}.pdf"'},
    )


@app.get("/{institution_id}/fhir/{resource_type}")
async def search_resources(
    institution_id: str, resource_type: str, request: Request
) -> JSONResponse:
    if resource_type not in OPTIONAL_RESOURCE_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    fixture = _institution(institution_id)
    claims = _bearer(request, institution_id, f"patient/{resource_type}.read")
    _reject_subject_param(request, claims)
    await _apply_fault(request, claims, institution_id)
    return _search(fixture, resource_type, claims, request)
