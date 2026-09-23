"""Field-level encryption for document metadata (Epic 5.1).

`documents` stores title, notes and original filename as ciphertext
(`*_ciphertext` columns) with a single `metadata_key_version` per row. This
module is the only place that turns those plaintext strings into ciphertext and
back, so the key material and the wire format live in exactly one spot.

Wire format: ``nonce(12 bytes) || AES-256-GCM(ciphertext || tag)``. The nonce is
random per call, so encrypting the same value twice yields different bytes.

Keys are loaded from the environment, never hard-coded:

  ``METADATA_ENCRYPTION_KEYS``        JSON ``{"1": "<base64 32-byte key>", ...}``
  ``METADATA_ENCRYPTION_KEY_VERSION``  integer; the version new writes use
                                       (defaults to the highest key present).

Keeping every historical key in the map lets us rotate the write version while
still decrypting rows written under an older one.
"""
import base64
import json
import os
import threading
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12
_KEY_BYTES = 32

_lock = threading.Lock()
_keyring: "_Keyring | None" = None


@dataclass(frozen=True)
class _Keyring:
    keys: dict[int, bytes]
    write_version: int


class MetadataCryptoError(RuntimeError):
    """Raised when keys are missing/misconfigured or a value cannot be decrypted."""


def _load_keyring() -> _Keyring:
    raw = os.environ.get("METADATA_ENCRYPTION_KEYS")
    if not raw:
        raise MetadataCryptoError("METADATA_ENCRYPTION_KEYS is not configured")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataCryptoError("METADATA_ENCRYPTION_KEYS is not valid JSON") from exc

    keys: dict[int, bytes] = {}
    for version, encoded in parsed.items():
        try:
            key = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise MetadataCryptoError(f"key version {version} is not valid base64") from exc
        if len(key) != _KEY_BYTES:
            raise MetadataCryptoError(f"key version {version} must be 32 bytes")
        keys[int(version)] = key

    if not keys:
        raise MetadataCryptoError("METADATA_ENCRYPTION_KEYS contains no keys")

    configured = os.environ.get("METADATA_ENCRYPTION_KEY_VERSION")
    write_version = int(configured) if configured else max(keys)
    if write_version not in keys:
        raise MetadataCryptoError(
            f"METADATA_ENCRYPTION_KEY_VERSION {write_version} has no matching key"
        )
    return _Keyring(keys=keys, write_version=write_version)


def _get_keyring() -> _Keyring:
    global _keyring
    if _keyring is None:
        with _lock:
            if _keyring is None:
                _keyring = _load_keyring()
    return _keyring


def reset_cache() -> None:
    """Drop the cached keyring so a later call re-reads the environment (tests)."""
    global _keyring
    with _lock:
        _keyring = None


def current_key_version() -> int:
    """The key version new writes will be tagged with."""
    return _get_keyring().write_version


def encrypt(plaintext: str, *, key_version: int | None = None) -> tuple[bytes, int]:
    """Encrypt a metadata string. Returns (ciphertext_blob, key_version)."""
    keyring = _get_keyring()
    version = keyring.write_version if key_version is None else key_version
    key = keyring.keys.get(version)
    if key is None:
        raise MetadataCryptoError(f"no key for version {version}")
    nonce = os.urandom(_NONCE_BYTES)
    blob = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + blob, version


def decrypt(ciphertext: bytes, key_version: int) -> str:
    """Decrypt a metadata blob produced by :func:`encrypt`."""
    keyring = _get_keyring()
    key = keyring.keys.get(key_version)
    if key is None:
        raise MetadataCryptoError(f"no key for version {key_version}")
    if len(ciphertext) <= _NONCE_BYTES:
        raise MetadataCryptoError("ciphertext is too short to contain a nonce")
    nonce, blob = ciphertext[:_NONCE_BYTES], ciphertext[_NONCE_BYTES:]
    try:
        plaintext = AESGCM(key).decrypt(nonce, blob, None)
    except Exception as exc:  # InvalidTag and friends
        raise MetadataCryptoError("could not decrypt metadata value") from exc
    return plaintext.decode("utf-8")
