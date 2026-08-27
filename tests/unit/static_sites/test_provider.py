"""Unit tests for app/static_sites/provider.py — extraction/placement logic
(no DB, no domain/SSL — that's covered in test_service.py with mocks)."""
from __future__ import annotations

import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from app.static_sites.provider import (
    StaticDeployError,
    deployment_directory,
    extract_upload,
)


@pytest.mark.unit
def test_html_upload_becomes_index_html(tmp_path: Path):
    upload = tmp_path / "upload.html"
    upload.write_text("<html>hello</html>")
    dest = tmp_path / "dest"

    result = extract_upload(upload_path=upload, source_type="html", dest_dir=dest)

    assert (dest / "index.html").read_text() == "<html>hello</html>"
    assert result["file_count"] == 1


@pytest.mark.unit
def test_zip_upload_with_root_index_html(tmp_path: Path):
    zpath = tmp_path / "site.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("index.html", "<html>root</html>")
        zf.writestr("style.css", "body{}")
    dest = tmp_path / "dest"

    result = extract_upload(upload_path=zpath, source_type="zip", dest_dir=dest)

    assert (dest / "index.html").is_file()
    assert (dest / "style.css").is_file()
    assert result["file_count"] == 2


@pytest.mark.unit
def test_zip_missing_index_html_raises(tmp_path: Path):
    zpath = tmp_path / "nosite.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("about.html", "<html>about</html>")
    dest = tmp_path / "dest"

    with pytest.raises(StaticDeployError, match="index.html was not found"):
        extract_upload(upload_path=zpath, source_type="zip", dest_dir=dest)


@pytest.mark.unit
def test_zip_single_wrapper_directory_is_flattened(tmp_path: Path):
    """Common `Export as ZIP` shape: everything nested one folder deep."""
    zpath = tmp_path / "wrapped.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("mysite/index.html", "<html>wrapped</html>")
        zf.writestr("mysite/assets/logo.png", b"\x89PNG")
    dest = tmp_path / "dest"

    result = extract_upload(upload_path=zpath, source_type="zip", dest_dir=dest)

    assert (dest / "index.html").read_text() == "<html>wrapped</html>"
    assert (dest / "assets" / "logo.png").is_file()
    assert not (dest / "mysite").exists()
    assert result["file_count"] == 2


@pytest.mark.unit
def test_zip_path_traversal_raises_static_deploy_error(tmp_path: Path):
    """A malicious zip must surface as StaticDeployError (safe message), not
    a raw UnsafeArchiveError leaking internals up through the pipeline."""
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")
    dest = tmp_path / "dest"

    with pytest.raises(StaticDeployError, match="Archive rejected"):
        extract_upload(upload_path=zpath, source_type="zip", dest_dir=dest)
    assert not (tmp_path.parent / "evil.txt").exists()


@pytest.mark.unit
def test_deployment_directory_uses_only_server_generated_ids(tmp_path, monkeypatch):
    """Directory layout must be <root>/<workspace>/<site>/<deployment>, built
    purely from UUIDs — never from a hostname, filename, or site name."""
    monkeypatch.setattr("app.static_sites.provider.static_site_root", lambda: tmp_path)
    ws, site, dep = uuid4(), uuid4(), uuid4()

    path = deployment_directory(ws, site, dep)

    assert path == (tmp_path.resolve() / str(ws) / str(site) / str(dep))
