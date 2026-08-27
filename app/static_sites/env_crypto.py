"""Authenticated encryption for static-site environment variable values.

Reuses the SAME key-derivation convention already used twice in this
repository — app/enterprise/service.py's ``EnterpriseService._fernet()``
(SSO client secrets) and app/studio/deploy.py's ``_fernet()``
(.env.production at-rest encryption): a Fernet key derived from
``settings.JWT_SECRET_KEY`` via SHA-256 + urlsafe-base64. Phase 4A
deliberately does not introduce a third, independent key-management scheme —
JWT_SECRET_KEY is already a mandatory, strength-checked application secret
(see app/config/settings.py's ``_enforce_production_secrets`` validator), so
this gives every deployment "comes from secure application configuration"
and "fails closed if missing" for free rather than reinventing it.

Nothing here ever logs or raises with plaintext — encrypt/decrypt failures
are collapsed into ``EnvVarCryptoError`` with a fixed, generic message.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import settings


class EnvVarCryptoError(Exception):
    """Raised on any encryption/decryption failure. Message is always safe
    to log or return to a client — never includes plaintext, ciphertext, or
    the encryption key."""


def _fernet() -> Fernet:
    key_material = (settings.JWT_SECRET_KEY or "").strip()
    if not key_material:
        # Fail closed: never fall back to a hardcoded/default key.
        raise EnvVarCryptoError(
            "Environment variable encryption is unavailable: no encryption key is configured."
        )
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(plaintext: str) -> str:
    """Encrypt an environment variable value for storage. Returns an opaque
    token string safe to store in ``encrypted_value``. Raises
    EnvVarCryptoError (never the plaintext) on any failure."""
    try:
        token = _fernet().encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")
    except EnvVarCryptoError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EnvVarCryptoError("Failed to encrypt environment variable value.") from exc


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a stored ``encrypted_value`` back to plaintext. Internal use
    only (service layer / future build-injection phases) — API responses
    must never call this and return the result. Raises EnvVarCryptoError
    (never the ciphertext or key) on any failure, including a token that was
    encrypted under a different/rotated key."""
    try:
        token = _fernet().decrypt(encrypted_value.encode("ascii"))
        return token.decode("utf-8")
    except EnvVarCryptoError:
        raise
    except InvalidToken as exc:
        raise EnvVarCryptoError("Failed to decrypt environment variable value.") from exc
    except Exception as exc:  # noqa: BLE001
        raise EnvVarCryptoError("Failed to decrypt environment variable value.") from exc
