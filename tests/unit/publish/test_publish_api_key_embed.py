"""Unit tests: publish embed never leaves YOUR_KEY; reuse vs re-issue."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.agent_platform.publish.service import KEY_PREFIX, PublishService, hash_api_key


def _svc_with_repo(repo: MagicMock) -> PublishService:
    svc = PublishService.__new__(PublishService)
    svc.db = MagicMock()
    svc.repo = repo
    return svc


def test_resolve_creates_key_when_none_active():
    repo = MagicMock()
    repo.get_active_key_for_agent.return_value = None
    raw = f"{KEY_PREFIX}abc"
    record = SimpleNamespace(id=uuid4(), key_hash=hash_api_key(raw), key_prefix=raw[:16])
    repo_create = MagicMock(return_value=(raw, record))

    svc = _svc_with_repo(repo)
    svc._create_key_record = repo_create  # type: ignore[method-assign]

    out_raw, out_rec = svc._resolve_publish_api_key(uuid4(), uuid4())
    assert out_raw == raw
    assert out_rec is record
    assert "YOUR_KEY" not in out_raw
    repo_create.assert_called_once()


def test_resolve_reuses_matching_known_plaintext():
    known = f"{KEY_PREFIX}knownsecretvalue"
    active = SimpleNamespace(
        id=uuid4(),
        key_hash=hash_api_key(known),
        key_prefix=known[:16],
        is_active=True,
        revoked_at=None,
    )
    repo = MagicMock()
    repo.get_active_key_for_agent.return_value = active

    svc = _svc_with_repo(repo)
    svc._create_key_record = MagicMock()  # type: ignore[method-assign]

    out_raw, out_rec = svc._resolve_publish_api_key(
        uuid4(), uuid4(), known_api_key=known
    )
    assert out_raw == known
    assert out_rec is active
    svc._create_key_record.assert_not_called()
    repo.revoke_key.assert_not_called()


def test_resolve_reissues_single_key_without_plaintext():
    old = SimpleNamespace(
        id=uuid4(),
        key_hash=hash_api_key(f"{KEY_PREFIX}old"),
        key_prefix="tht_live_old",
        is_active=True,
        revoked_at=None,
    )
    new_raw = f"{KEY_PREFIX}newsecret"
    new_rec = SimpleNamespace(id=uuid4(), key_hash=hash_api_key(new_raw), key_prefix=new_raw[:16])

    repo = MagicMock()
    repo.get_active_key_for_agent.return_value = old
    repo.list_keys.return_value = [old]

    svc = _svc_with_repo(repo)
    svc._create_key_record = MagicMock(return_value=(new_raw, new_rec))  # type: ignore[method-assign]

    out_raw, out_rec = svc._resolve_publish_api_key(uuid4(), uuid4())
    assert out_raw == new_raw
    assert out_rec is new_rec
    assert "YOUR_KEY" not in out_raw
    repo.revoke_key.assert_called_once_with(old)
    svc._create_key_record.assert_called_once()


def test_build_embed_script_never_uses_placeholder_when_given_live_key():
    svc = _svc_with_repo(MagicMock())
    svc._base_url = lambda: "https://api.thtwaat.com"  # type: ignore[method-assign]
    key = f"{KEY_PREFIX}reallivekeyvalue"
    script = svc.build_embed_script(key)
    assert f'data-api-key="{key}"' in script
    assert "YOUR_KEY" not in script
