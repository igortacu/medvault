"""Field validation for sign-up and password reset (Epic 1, stories 1 and 3).

Pure functions, no I/O. Each returns the normalised value or raises ValueError with a
user-facing message; `collect_errors` gathers them into a field -> message map.
"""
import re
import unicodedata
from datetime import date

NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\u2019\-][^\W\d_]+)*$")
PHONE_RE = re.compile(r"^\+373[0-9]{8}$")

PASSWORD_MIN = 10
PASSWORD_MAX = 128

# Small offline blocklist; a breached-password API check can replace this later.
_COMMON_PASSWORDS = frozenset(
    p.lower()
    for p in (
        "password1!", "password123!", "Password1234", "Qwerty12345!", "Welcome123!",
        "Admin12345!", "Letmein1234!", "Iloveyou123!", "Passw0rd123!", "Medvault123!",
        "Chisinau2024!", "Moldova12345!", "P@ssw0rd123", "Qwertyuiop1!", "Abcdefg1234!",
    )
)


def validate_name(value: str) -> str:
    # NFC so "Ș" typed as S + combining comma matches the precomposed letter.
    value = unicodedata.normalize("NFC", (value or "").strip())
    if not 2 <= len(value) <= 50:
        raise ValueError("Must be between 2 and 50 characters.")
    if not NAME_RE.match(value):
        raise ValueError("Use letters only (spaces, hyphens and apostrophes are allowed).")
    return value


def normalize_phone(value: str) -> str:
    """Accept +373XXXXXXXX, 373XXXXXXXX or 0XXXXXXXX; return +373XXXXXXXX."""
    raw = re.sub(r"[\s\-().]", "", value or "")
    if raw.startswith("00373"):
        raw = "+" + raw[2:]
    elif raw.startswith("373"):
        raw = "+" + raw
    elif re.fullmatch(r"0[0-9]{8}", raw):
        raw = "+373" + raw[1:]
    if not PHONE_RE.match(raw):
        raise ValueError("Enter a valid Moldovan phone number (+373XXXXXXXX).")
    return raw


def validate_dob(value: date) -> date:
    today = date.today()
    if value > today:
        raise ValueError("Date of birth cannot be in the future.")
    try:
        oldest = today.replace(year=today.year - 120)
    except ValueError:  # 29 Feb
        oldest = today.replace(year=today.year - 120, day=28)
    if value < oldest:
        raise ValueError("Enter a valid date of birth.")
    return value


def validate_password(value: str) -> str:
    value = value or ""
    if not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
        raise ValueError(f"Must be between {PASSWORD_MIN} and {PASSWORD_MAX} characters.")
    if not re.search(r"[a-z]", value):
        raise ValueError("Must contain a lowercase letter.")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Must contain an uppercase letter.")
    if not re.search(r"[0-9]", value):
        raise ValueError("Must contain a digit.")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("Must contain a special character.")
    if value.lower() in _COMMON_PASSWORDS:
        raise ValueError("This password is too common. Choose another one.")
    return value


def collect_errors(checks: dict[str, tuple]) -> tuple[dict, dict[str, str]]:
    """checks: field -> (validator, raw_value). Returns (clean values, errors)."""
    clean: dict = {}
    errors: dict[str, str] = {}
    for field, (fn, raw) in checks.items():
        try:
            clean[field] = fn(raw)
        except ValueError as exc:
            errors[field] = str(exc)
    return clean, errors
