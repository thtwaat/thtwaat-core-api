"""Safe ZIP extraction for untrusted (user-uploaded) archives.

Never call zipfile.ZipFile.extractall() on untrusted input — it happily
writes through `../` traversal, absolute paths, and (on POSIX) symlink
entries. This module validates every entry *before* writing any bytes
(fail closed, nothing partially written on a bad archive) and re-checks
every resolved path stays inside the caller-supplied deployment root.

Callers must not pre-create arbitrary files inside dest_dir based on
attacker-controlled names; dest_dir itself must be a server-generated,
already-isolated path (see app/static_sites).
"""
from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import List


class UnsafeArchiveError(ValueError):
    """Raised when an archive is malformed, oversized, or contains an unsafe entry."""


# Conservative defaults — callers (app/static_sites) override via settings.
DEFAULT_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_EXTRACTED_BYTES = 200 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_FILE_COUNT = 5000
# Per-entry uncompressed:compressed ratio above which we treat the entry as a
# likely decompression bomb (only enforced once the entry is non-trivially
# sized, so tiny highly-compressible text files don't false-positive).
DEFAULT_MAX_COMPRESSION_RATIO = 100
_RATIO_CHECK_MIN_BYTES = 1 * 1024 * 1024
_READ_CHUNK = 1024 * 1024


@dataclass
class ExtractResult:
    root: Path
    file_count: int
    total_bytes: int
    files: List[str] = field(default_factory=list)


def _is_symlink_entry(info: zipfile.ZipInfo) -> bool:
    # Unix permission bits are packed into the top 16 bits of external_attr
    # when the archive was created on a POSIX system; Windows-created zips
    # never set this, so it's a safe no-op check there.
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _normalize_member_name(name: str) -> str:
    """Reject unsafe member names; return a POSIX-relative normalized name."""
    if not name or not name.strip():
        raise UnsafeArchiveError("archive contains an empty entry name")

    raw = name.replace("\\", "/")

    # Windows drive-letter absolute path (C:/..., C:\...) or UNC (\\server\share)
    if PureWindowsPath(name).drive or raw.startswith("//"):
        raise UnsafeArchiveError(f"unsafe entry (drive/UNC path): {name!r}")

    # POSIX absolute path
    if raw.startswith("/"):
        raise UnsafeArchiveError(f"unsafe entry (absolute path): {name!r}")

    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if not parts:
        raise UnsafeArchiveError(f"unsafe entry (empty after normalization): {name!r}")
    if any(p == ".." for p in parts):
        raise UnsafeArchiveError(f"unsafe entry (path traversal): {name!r}")

    return "/".join(parts)


def safe_extract_zip(
    zip_path: Path,
    dest_dir: Path,
    *,
    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
    max_extracted_bytes: int = DEFAULT_MAX_EXTRACTED_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_file_count: int = DEFAULT_MAX_FILE_COUNT,
    max_compression_ratio: int = DEFAULT_MAX_COMPRESSION_RATIO,
) -> ExtractResult:
    """Validate and extract an untrusted ZIP into dest_dir.

    Two-pass: every entry is validated (name, size, ratio, symlink bit,
    resolved-path containment) before any bytes are written, so a bad
    archive fails clean without leaving partial output. dest_dir must
    already exist and be an isolated, server-generated directory.
    """
    zip_path = Path(zip_path)
    dest_dir = Path(dest_dir)

    if not zip_path.is_file():
        raise UnsafeArchiveError("archive file not found")

    archive_size = zip_path.stat().st_size
    if archive_size == 0:
        raise UnsafeArchiveError("archive is empty")
    if archive_size > max_archive_bytes:
        raise UnsafeArchiveError(
            f"archive too large ({archive_size} bytes > {max_archive_bytes} limit)"
        )

    if not zipfile.is_zipfile(zip_path):
        raise UnsafeArchiveError("malformed or unsupported archive")

    dest_dir.mkdir(parents=True, exist_ok=True)
    base = dest_dir.resolve()

    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile as exc:
        raise UnsafeArchiveError("malformed archive") from exc

    with zf:
        # Deliberately no zf.testzip() here: it unconditionally decompresses
        # every entry to completion (in chunks, so it won't spike memory, but
        # it WILL spin the CPU for as long as the entry takes to decompress)
        # before any of our own size/ratio limits below get a chance to
        # reject a bomb based on cheap central-directory metadata alone. A
        # crafted entry with a tiny compressed size and a massive declared
        # size would make testzip() hang/burn CPU on exactly the kind of
        # input this function exists to reject instantly. CRC verification
        # still happens per-file during the bounded pass-2 read below (zipfile
        # raises BadZipFile at end-of-stream on mismatch), which we catch.
        try:
            infos = zf.infolist()
        except (zipfile.BadZipFile, EOFError, OSError) as exc:
            raise UnsafeArchiveError("malformed archive") from exc

        planned: List[tuple] = []  # (info, normalized_name, resolved_path, is_dir)
        total_extracted = 0
        file_count = 0

        for info in infos:
            is_dir = info.filename.endswith("/") or (info.external_attr >> 16) & 0o40000
            if _is_symlink_entry(info):
                raise UnsafeArchiveError(f"unsafe entry (symlink not allowed): {info.filename!r}")

            normalized = _normalize_member_name(info.filename)
            candidate = base / normalized
            resolved = candidate.resolve()
            try:
                resolved.relative_to(base)
            except ValueError:
                raise UnsafeArchiveError(f"unsafe entry (escapes destination): {info.filename!r}")

            if is_dir:
                planned.append((info, normalized, resolved, True))
                continue

            file_count += 1
            if file_count > max_file_count:
                raise UnsafeArchiveError(
                    f"archive contains too many files (> {max_file_count} limit)"
                )

            declared_size = int(info.file_size)
            if declared_size > max_file_bytes:
                raise UnsafeArchiveError(
                    f"file too large in archive: {info.filename!r} "
                    f"({declared_size} bytes > {max_file_bytes} limit)"
                )

            compressed = max(int(info.compress_size), 1)
            if declared_size >= _RATIO_CHECK_MIN_BYTES:
                ratio = declared_size / compressed
                if ratio > max_compression_ratio:
                    raise UnsafeArchiveError(
                        f"suspicious compression ratio for {info.filename!r} "
                        f"({ratio:.1f}x > {max_compression_ratio}x limit) — possible zip bomb"
                    )

            total_extracted += declared_size
            if total_extracted > max_extracted_bytes:
                raise UnsafeArchiveError(
                    f"archive expands beyond the allowed total "
                    f"({total_extracted} bytes > {max_extracted_bytes} limit)"
                )

            planned.append((info, normalized, resolved, False))

        # Nothing written yet — every entry validated. Now extract for real,
        # re-checking actual decompressed bytes against the declared size so a
        # header that understates file_size can't be used to smuggle a bomb
        # past the pass-1 size check.
        written_files: List[str] = []
        written_bytes = 0
        for info, normalized, resolved, is_dir in planned:
            if is_dir:
                resolved.mkdir(parents=True, exist_ok=True)
                continue

            resolved.parent.mkdir(parents=True, exist_ok=True)
            if resolved.exists() and (resolved.is_symlink() or _has_junction(resolved)):
                raise UnsafeArchiveError(f"refusing to overwrite link at {normalized!r}")

            declared_size = int(info.file_size)
            actual = 0
            try:
                with zf.open(info, "r") as src, open(resolved, "wb") as dst:
                    while True:
                        chunk = src.read(_READ_CHUNK)
                        if not chunk:
                            break
                        actual += len(chunk)
                        if actual > declared_size + _READ_CHUNK or actual > max_file_bytes:
                            raise UnsafeArchiveError(
                                f"decompressed size exceeds declared/allowed size for {normalized!r}"
                            )
                        dst.write(chunk)
            except UnsafeArchiveError:
                raise
            except (zipfile.BadZipFile, EOFError, OSError, RuntimeError) as exc:
                # zipfile raises BadZipFile at end-of-stream on a CRC
                # mismatch — surface it as the same clean, sanitized error
                # type as every other rejection reason.
                raise UnsafeArchiveError(f"malformed archive (corrupt entry: {normalized!r})") from exc

            written_bytes += actual
            written_files.append(normalized)

        return ExtractResult(root=base, file_count=len(written_files), total_bytes=written_bytes, files=written_files)


def _has_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction()) if callable(is_junction) else False
