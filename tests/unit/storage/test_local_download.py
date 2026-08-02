"""Unit tests for local storage path confinement (P0 download hardening)."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.storage.local_paths import UnsafeLocalPathError, resolve_safe_local_path
from app.storage.model import StorageProvider
from app.storage.service import StorageService


@pytest.mark.unit
def test_resolve_valid_file(tmp_path: Path):
    base = tmp_path / "uploads"
    base.mkdir()
    target = base / "abc123.txt"
    target.write_bytes(b"hello")

    resolved = resolve_safe_local_path(base_dir=base, storage_filename="abc123.txt")
    assert resolved == target.resolve()
    assert resolved.read_bytes() == b"hello"


@pytest.mark.unit
@pytest.mark.parametrize(
    "filename",
    [
        "../secret.txt",
        "..\\secret.txt",
        "foo/../secret.txt",
        "/etc/passwd",
        "subdir/file.txt",
        "./../outside.txt",
        "",
    ],
)
def test_resolve_rejects_path_traversal(tmp_path: Path, filename: str):
    base = tmp_path / "uploads"
    base.mkdir()
    with pytest.raises((UnsafeLocalPathError, FileNotFoundError)):
        resolve_safe_local_path(base_dir=base, storage_filename=filename)


@pytest.mark.unit
def test_resolve_rejects_symlink_escape(tmp_path: Path):
    base = tmp_path / "uploads"
    base.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret", encoding="utf-8")
    link = base / "link.txt"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlink creation not permitted on this host")

    with pytest.raises(UnsafeLocalPathError):
        resolve_safe_local_path(base_dir=base, storage_filename="link.txt")


@pytest.mark.unit
def test_resolve_missing_file(tmp_path: Path):
    base = tmp_path / "uploads"
    base.mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_safe_local_path(base_dir=base, storage_filename="missing.txt")


@pytest.mark.unit
def test_download_file_serves_local_file_response(tmp_path: Path, monkeypatch):
    base = tmp_path / "uploads"
    base.mkdir()
    name = f"{uuid.uuid4().hex}.txt"
    (base / name).write_bytes(b"payload")

    company_id = uuid.uuid4()
    db_file = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        storage_filename=name,
        original_filename="doc.txt",
        mime_type="text/plain",
        provider=StorageProvider.LOCAL,
        storage_path=str(base / name),
    )

    svc = StorageService(db=MagicMock())
    svc.repo = MagicMock()
    svc.repo.get_by_id.return_value = db_file
    monkeypatch.setattr(
        "app.storage.service.storage_settings.LOCAL_STORAGE_DIR",
        str(base),
    )

    response = svc.download_file(db_file.id, company_id)
    assert isinstance(response, FileResponse)
    assert Path(response.path).read_bytes() == b"payload"


@pytest.mark.unit
def test_download_foreign_company_returns_404():
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    db_file = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_a,
        storage_filename="x.txt",
        provider=StorageProvider.LOCAL,
    )
    svc = StorageService(db=MagicMock())
    svc.repo = MagicMock()
    svc.repo.get_by_id.return_value = db_file

    with pytest.raises(HTTPException) as exc:
        svc.download_file(db_file.id, company_b)
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_download_missing_returns_404():
    svc = StorageService(db=MagicMock())
    svc.repo = MagicMock()
    svc.repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        svc.download_file(uuid.uuid4(), uuid.uuid4())
    assert exc.value.status_code == 404
