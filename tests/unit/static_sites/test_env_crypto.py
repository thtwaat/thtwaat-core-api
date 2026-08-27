"""Unit tests for app/static_sites/env_crypto.py — the Fernet-based
encryption/decryption used to store static-site environment variable values
at rest. No database or FastAPI app involved."""
from __future__ import annotations

import pytest

from app.static_sites.env_crypto import EnvVarCryptoError, decrypt_value, encrypt_value

SECRET_PLAINTEXT = "SUPER_SECRET_123456"


@pytest.mark.unit
def test_encrypt_then_decrypt_round_trip():
    token = encrypt_value(SECRET_PLAINTEXT)
    assert token != SECRET_PLAINTEXT
    assert decrypt_value(token) == SECRET_PLAINTEXT


@pytest.mark.unit
def test_encrypted_token_never_contains_plaintext_bytes():
    token = encrypt_value(SECRET_PLAINTEXT)
    assert SECRET_PLAINTEXT not in token
    assert SECRET_PLAINTEXT.encode("utf-8") not in token.encode("ascii")


@pytest.mark.unit
def test_decrypt_invalid_token_raises_generic_crypto_error():
    with pytest.raises(EnvVarCryptoError) as exc:
        decrypt_value("not-a-real-fernet-token")
    # Message must be generic — never echoes the invalid input back.
    assert "not-a-real-fernet-token" not in str(exc.value)


@pytest.mark.unit
def test_missing_encryption_key_fails_closed(monkeypatch):
    from app.static_sites import env_crypto

    monkeypatch.setattr(env_crypto.settings, "JWT_SECRET_KEY", "")
    with pytest.raises(EnvVarCryptoError) as exc:
        encrypt_value(SECRET_PLAINTEXT)
    assert SECRET_PLAINTEXT not in str(exc.value)


@pytest.mark.unit
def test_missing_encryption_key_fails_closed_on_decrypt(monkeypatch):
    from app.static_sites import env_crypto

    token = encrypt_value(SECRET_PLAINTEXT)
    monkeypatch.setattr(env_crypto.settings, "JWT_SECRET_KEY", None)
    with pytest.raises(EnvVarCryptoError):
        decrypt_value(token)


@pytest.mark.unit
def test_different_keys_cannot_decrypt_each_others_tokens(monkeypatch):
    from app.static_sites import env_crypto

    monkeypatch.setattr(env_crypto.settings, "JWT_SECRET_KEY", "key-one-32-characters-long-abcd!")
    token = encrypt_value(SECRET_PLAINTEXT)

    monkeypatch.setattr(env_crypto.settings, "JWT_SECRET_KEY", "key-two-different-32-chars-wxyz!")
    with pytest.raises(EnvVarCryptoError):
        decrypt_value(token)
