"""Backup + restore helpers for DB, uploads, knowledge."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


def backup_root() -> Path:
    root = Path(getattr(settings, "BACKUP_DIR", "data/backups"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def retention_days() -> int:
    return int(getattr(settings, "BACKUP_RETENTION_DAYS", 14) or 14)


def run_database_backup() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = backup_root() / f"db_{ts}.sql.gz"
    url = settings.database_url
    # Prefer pg_dump via docker if host tools missing
    cmd = f'pg_dump "{url}" | gzip > "{out}"'
    try:
        subprocess.run(cmd, shell=True, check=True, timeout=600)
        logger.info("backup_db path=%s", out)
        return out
    except Exception as exc:
        # Fallback: docker compose exec
        try:
            alt = [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "pg_dump",
                "-U",
                settings.db_user or "postgres",
                settings.db_name or "thtwaat",
            ]
            with open(out.with_suffix(""), "wb") as f:
                r = subprocess.run(alt, capture_output=True, timeout=600)
                f.write(r.stdout)
            # gzip
            import gzip

            raw = out.with_suffix("")
            with open(raw, "rb") as src, gzip.open(out, "wb") as dst:
                dst.write(src.read())
            raw.unlink(missing_ok=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode() if r.stderr else "pg_dump failed")
            return out
        except Exception as exc2:
            logger.error("database backup failed: %s / %s", exc, exc2)
            raise


def run_filesystem_backup(label: str, source: Path) -> Optional[Path]:
    if not source.exists():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = backup_root() / f"{label}_{ts}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(source, arcname=source.name)
    logger.info("backup_fs label=%s path=%s", label, out)
    return out


def run_full_backup() -> Dict[str, str]:
    results: Dict[str, str] = {}
    try:
        results["database"] = str(run_database_backup())
    except Exception as exc:
        results["database_error"] = str(exc)

    uploads = run_filesystem_backup("uploads", Path(settings.LOCAL_STORAGE_DIR))
    if uploads:
        results["uploads"] = str(uploads)
    knowledge = run_filesystem_backup("knowledge", Path("data/knowledge"))
    if knowledge:
        results["knowledge"] = str(knowledge)

    prune_old_backups()
    return results


def prune_old_backups() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days())
    removed = 0
    for path in backup_root().glob("*"):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def list_backups() -> List[Dict[str, str]]:
    items = []
    for path in sorted(backup_root().glob("*"), reverse=True):
        if path.is_file():
            items.append({
                "name": path.name,
                "path": str(path),
                "size_bytes": str(path.stat().st_size),
                "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
    return items


def restore_filesystem(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(path=dest.parent)
    logger.info("restore_fs archive=%s dest=%s", archive, dest)
