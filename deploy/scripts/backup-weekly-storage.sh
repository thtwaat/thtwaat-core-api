#!/usr/bin/env bash
# Weekly storage (uploads + knowledge) archive with rotation.
set -euo pipefail

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
OUT_DIR="${ROOT}/backups/storage"
RETENTION_DAYS="${STORAGE_BACKUP_RETENTION_DAYS:-56}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${OUT_DIR}"

SRC_UPLOADS="${ROOT}/shared/data/uploads"
SRC_KNOWLEDGE="${ROOT}/shared/data/knowledge"
# Fallback to current release data paths
[[ -d "${SRC_UPLOADS}" ]] || SRC_UPLOADS="${ROOT}/current/data/uploads"
[[ -d "${SRC_KNOWLEDGE}" ]] || SRC_KNOWLEDGE="${ROOT}/current/data/knowledge"

OUT="${OUT_DIR}/storage_${STAMP}.tar.gz"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Weekly storage backup → ${OUT}"

tmpdir="$(mktemp -d)"
mkdir -p "${tmpdir}/data"
[[ -d "${SRC_UPLOADS}" ]] && cp -a "${SRC_UPLOADS}" "${tmpdir}/data/uploads" || mkdir -p "${tmpdir}/data/uploads"
[[ -d "${SRC_KNOWLEDGE}" ]] && cp -a "${SRC_KNOWLEDGE}" "${tmpdir}/data/knowledge" || mkdir -p "${tmpdir}/data/knowledge"
tar -czf "${OUT}" -C "${tmpdir}" data
rm -rf "${tmpdir}"

# Integrity
tar -tzf "${OUT}" >/dev/null
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Restore verify: tar listing OK"

find "${OUT_DIR}" -type f -name 'storage_*.tar.gz' -mtime "+${RETENTION_DAYS}" -delete || true
ls -lah "${OUT_DIR}" | tail -n 10
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Weekly storage backup complete"
