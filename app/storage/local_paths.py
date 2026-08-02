"""
Safe path resolution for local-disk downloads.

Keeps files confined to LOCAL_STORAGE_DIR and blocks traversal / symlink escape.
"""
from __future__ import annotations

from pathlib import Path


class UnsafeLocalPathError(ValueError):
    """Raised when a storage filename would escape the upload root."""


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction()) if callable(is_junction) else False


def resolve_safe_local_path(*, base_dir: Path | str, storage_filename: str) -> Path:
    """
    Resolve ``storage_filename`` under ``base_dir``.

    Rules:
    - filename must be a single path segment (no directories, no ``..``)
    - path must remain inside the resolved base directory
    - symlinks/junctions are rejected (blocks symlink escape)
    - target must exist and be a regular file
    """
    if not storage_filename or not str(storage_filename).strip():
        raise UnsafeLocalPathError("empty storage filename")

    raw = str(storage_filename).strip()
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        raise UnsafeLocalPathError("absolute storage filename")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if len(parts) != 1 or parts[0] != Path(raw).name:
        raise UnsafeLocalPathError("path traversal in storage filename")
    if parts[0] in (".", "..") or ".." in parts[0]:
        raise UnsafeLocalPathError("parent path segment")

    base = Path(base_dir).resolve()
    candidate = base / parts[0]

    # Refuse links before following them (symlink / junction escape).
    if _is_link(candidate):
        raise UnsafeLocalPathError("symlinks are not allowed for download")

    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(str(candidate))

    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(base):
        raise UnsafeLocalPathError("path escapes storage root")
    if not resolved.is_file() or _is_link(resolved):
        raise UnsafeLocalPathError("resolved path is not a safe regular file")

    return resolved
