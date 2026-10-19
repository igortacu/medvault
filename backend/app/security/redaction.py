"""Scrubbing for anything that leaves the request: logs, error bodies, audit metadata.

Two layers, because neither is enough alone:

* by key: a field whose name says it is secret or medical (`idnp`, `access_token`,
  `filename`, `value`, ...) is replaced wholesale, whatever it holds;
* by shape: free text is searched for IDNP-like numbers, phone numbers, bearer
  tokens, JWT/Fernet tokens and secret query parameters.

Medical values have no recognisable shape, so they are only caught by key: never
log a record's contents in a message string, pass ids and counts instead.
"""
import re
from collections.abc import Mapping

REDACTED = "[REDACTED]"

SENSITIVE_KEYS = frozenset(
    {
        # identity
        "idnp", "phone", "phone_e164", "date_of_birth", "first_name", "last_name",
        # credentials and tokens
        "password", "new_password", "password_hash", "code", "otp", "token",
        "access_token", "refresh_token", "id_token", "reset_token", "session_id",
        "client_secret", "code_verifier", "authorization", "cookie", "set-cookie",
        "challenge_id", "request_uri", "state",
        # document and medical content
        "filename", "file_name", "original_filename", "title", "notes", "content",
        "value", "values", "valuequantity", "value_quantity", "valuestring",
        "result", "results", "observation", "observations", "diagnosis",
        "interpretation", "reference_range", "weight_kg", "height_cm",
    }
)

_PATTERNS = (
    # Secret query parameters / form fields: keep the name, drop the value.
    (
        re.compile(
            r"(?i)\b(idnp|code|state|token|access_token|refresh_token|reset_token|"
            r"request_uri|session_id|challenge_id|code_verifier|client_secret|password)"
            r"=([^&\s\"',;]+)"
        ),
        lambda m: f"{m.group(1)}={REDACTED}",
    ),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), lambda m: f"Bearer {REDACTED}"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), lambda m: REDACTED),  # JWT
    (re.compile(r"\bgAAAAA[\w-]{20,}=*"), lambda m: REDACTED),  # Fernet ciphertext
    # An IDNP is 13 digits; anything that long is treated as one.
    (re.compile(r"(?<!\d)\d{13}(?!\d)"), lambda m: REDACTED),
    # Phone numbers in E.164 (+373...) form.
    (re.compile(r"\+\d{8,15}\b"), lambda m: REDACTED),
)


def redact_text(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


_NORMALISED_KEYS = frozenset(k.replace("-", "_") for k in SENSITIVE_KEYS)


def _sensitive(key) -> bool:
    return isinstance(key, str) and key.lower().replace("-", "_") in _NORMALISED_KEYS


def redact(value):
    """Recursively scrub a structure (dicts by key, strings by shape)."""
    if isinstance(value, Mapping):
        return {k: REDACTED if _sensitive(k) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
