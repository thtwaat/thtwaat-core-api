"""Unit tests for safe untrusted-ZIP extraction (app/storage/safe_extract.py)."""
from __future__ import annotations

import io
import os
import stat
import zipfile
from pathlib import Path

import pytest

from app.storage.safe_extract import UnsafeArchiveError, safe_extract_zip


def _make_zip(path: Path, entries: dict[str, bytes], *, symlink: tuple[str, str] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
        if symlink:
            link_name, target = symlink
            info = zipfile.ZipInfo(link_name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, target)
    return path


@pytest.mark.unit
def test_normal_zip_extracts(tmp_path: Path):
    zpath = _make_zip(
        tmp_path / "site.zip",
        {"index.html": b"<html>hi</html>", "style.css": b"body{}"},
    )
    dest = tmp_path / "dest"

    result = safe_extract_zip(zpath, dest)

    assert result.file_count == 2
    assert (dest / "index.html").read_bytes() == b"<html>hi</html>"
    assert (dest / "style.css").read_bytes() == b"body{}"


@pytest.mark.unit
def test_nested_directories(tmp_path: Path):
    zpath = _make_zip(
        tmp_path / "site.zip",
        {
            "index.html": b"root",
            "assets/img/logo.png": b"\x89PNG",
            "css/deep/nested/style.css": b"body{}",
        },
    )
    dest = tmp_path / "dest"

    result = safe_extract_zip(zpath, dest)

    assert result.file_count == 3
    assert (dest / "assets" / "img" / "logo.png").read_bytes() == b"\x89PNG"
    assert (dest / "css" / "deep" / "nested" / "style.css").is_file()


@pytest.mark.unit
def test_path_traversal_rejected(tmp_path: Path):
    zpath = _make_zip(tmp_path / "evil.zip", {"../../evil.txt": b"pwned"})
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="traversal"):
        safe_extract_zip(zpath, dest)

    assert not (tmp_path / "evil.txt").exists()
    assert not any(dest.rglob("*")) if dest.exists() else True


@pytest.mark.unit
def test_path_traversal_mixed_with_safe_entries(tmp_path: Path):
    zpath = _make_zip(
        tmp_path / "evil2.zip",
        {"index.html": b"safe", "../outside.txt": b"pwned"},
    )
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(zpath, dest)

    # Fail-closed: nothing written even though index.html alone was safe.
    assert not (dest / "index.html").exists()


@pytest.mark.unit
def test_absolute_path_rejected(tmp_path: Path):
    zpath = _make_zip(tmp_path / "abs.zip", {"/etc/passwd": b"root:x:0:0"})
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="absolute"):
        safe_extract_zip(zpath, dest)


@pytest.mark.unit
def test_windows_drive_path_rejected(tmp_path: Path):
    zpath = _make_zip(tmp_path / "win.zip", {"C:\\Windows\\System32\\evil.dll": b"MZ"})
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="drive|UNC"):
        safe_extract_zip(zpath, dest)


@pytest.mark.unit
def test_windows_unc_path_rejected(tmp_path: Path):
    zpath = _make_zip(tmp_path / "unc.zip", {"//server/share/evil.txt": b"x"})
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(zpath, dest)


@pytest.mark.unit
def test_symlink_entry_rejected(tmp_path: Path):
    zpath = _make_zip(
        tmp_path / "link.zip",
        {"index.html": b"safe"},
        symlink=("evil_link", "/etc/passwd"),
    )
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="symlink"):
        safe_extract_zip(zpath, dest)

    assert not (dest / "index.html").exists()


@pytest.mark.unit
def test_zip_bomb_high_compression_ratio_rejected(tmp_path: Path):
    zpath = tmp_path / "bomb.zip"
    # 20MB of a single repeated byte compresses to a few KB — a textbook bomb pattern.
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", b"0" * (20 * 1024 * 1024))
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="compression ratio|zip bomb"):
        safe_extract_zip(zpath, dest, max_file_bytes=50 * 1024 * 1024)


@pytest.mark.unit
def test_excessive_extracted_size_rejected(tmp_path: Path):
    zpath = tmp_path / "big.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(5):
            # Incompressible-ish random-like content to avoid tripping the ratio check first.
            zf.writestr(f"file{i}.bin", os.urandom(200_000))
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="expands beyond|too large"):
        safe_extract_zip(zpath, dest, max_extracted_bytes=500_000, max_file_bytes=1_000_000)


@pytest.mark.unit
def test_excessive_file_count_rejected(tmp_path: Path):
    zpath = tmp_path / "many.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(50):
            zf.writestr(f"f{i}.txt", b"x")
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="too many files"):
        safe_extract_zip(zpath, dest, max_file_count=10)


@pytest.mark.unit
def test_oversized_individual_file_rejected(tmp_path: Path):
    zpath = tmp_path / "onebig.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge.bin", os.urandom(2_000_000))
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="too large"):
        safe_extract_zip(zpath, dest, max_file_bytes=1_000_000)


@pytest.mark.unit
def test_malformed_zip_rejected(tmp_path: Path):
    zpath = tmp_path / "malformed.zip"
    zpath.write_bytes(b"this is not a zip file at all, just garbage bytes")
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="malformed"):
        safe_extract_zip(zpath, dest)


@pytest.mark.unit
def test_empty_archive_rejected(tmp_path: Path):
    zpath = tmp_path / "empty.zip"
    zpath.write_bytes(b"")
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(zpath, dest)


@pytest.mark.unit
def test_oversized_archive_rejected_before_opening(tmp_path: Path):
    zpath = _make_zip(tmp_path / "small.zip", {"index.html": b"hi"})
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError, match="too large"):
        safe_extract_zip(zpath, dest, max_archive_bytes=10)


@pytest.mark.unit
def test_testzip_is_never_called_on_untrusted_input(tmp_path: Path, monkeypatch):
    """Regression: zipfile.ZipFile.testzip() unconditionally decompresses
    every entry to completion before returning — calling it on untrusted
    input lets a crafted entry (tiny compressed size, huge declared size)
    burn CPU/time before our own declared-size checks ever run. Prove it's
    never invoked at all."""
    called = {"count": 0}
    orig = zipfile.ZipFile.testzip

    def _tracking_testzip(self, *a, **kw):
        called["count"] += 1
        return orig(self, *a, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "testzip", _tracking_testzip)

    zpath = _make_zip(tmp_path / "site.zip", {"index.html": b"hello"})
    dest = tmp_path / "dest"
    safe_extract_zip(zpath, dest)

    assert called["count"] == 0, "testzip() must never be called on untrusted archives"


@pytest.mark.unit
def test_corrupted_entry_raises_unsafe_archive_error_not_raw_badzipfile(tmp_path: Path):
    """A structurally valid zip whose entry data fails CRC verification must
    surface as our own UnsafeArchiveError (sanitized, catchable by callers),
    never a raw zipfile.BadZipFile leaking out of safe_extract_zip."""
    zpath = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("index.html", b"hello world, this is valid content")

    # Corrupt the raw stored bytes in place without touching the central
    # directory's CRC, so decompression proceeds but CRC verification fails
    # at end-of-stream — exactly the case testzip() used to catch upfront.
    raw = bytearray(zpath.read_bytes())
    marker = b"hello world"
    idx = raw.find(marker)
    assert idx != -1
    raw[idx:idx + len(marker)] = b"HELLO WORLD"
    zpath.write_bytes(bytes(raw))

    dest = tmp_path / "dest"
    with pytest.raises(UnsafeArchiveError, match="malformed|corrupt"):
        safe_extract_zip(zpath, dest)


@pytest.mark.unit
def test_destination_never_escaped_even_with_clever_names(tmp_path: Path):
    # ZIP writers normally reject writing these names at all, so build the
    # archive by hand via a crafted central directory is overkill — instead
    # verify our own normalization catches the equivalent traversal forms.
    zpath = _make_zip(
        tmp_path / "clever.zip",
        {"a/b/../../../escape.txt": b"pwned"},
    )
    dest = tmp_path / "dest"

    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(zpath, dest)
