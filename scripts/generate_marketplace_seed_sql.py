"""Generate PostgreSQL seed + rollback SQL from marketplace JSON catalogs.

Usage:
  python scripts/generate_marketplace_seed_sql.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "data" / "marketplace" / "seeds"
INDEX = SEEDS / "index.json"
PACKAGES = SEEDS / "packages"
PACKAGES_INDEX = PACKAGES / "index.json"
SQL_DIR = ROOT / "data" / "marketplace" / "sql"

SEED_SQL = SQL_DIR / "001_seed_prompt_templates.sql"
UPGRADE_SQL = SQL_DIR / "002_upgrade_prompt_templates.sql"
ROLLBACK_SQL = SQL_DIR / "900_rollback_prompt_seeds.sql"

PACKAGE_SEED_SQL = SQL_DIR / "010_seed_package_templates.sql"
PACKAGE_UPGRADE_SQL = SQL_DIR / "011_upgrade_package_templates.sql"
PACKAGE_ROLLBACK_SQL = SQL_DIR / "910_rollback_package_seeds.sql"


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_json(obj) -> str:
    return _sql_str(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def _sql_text_array(tags: list) -> str:
    if not tags:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ", ".join(_sql_str(t) for t in tags) + "]::text[]"


def _sql_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _prompt_default_config(doc: dict) -> dict:
    return {
        "prompt": doc.get("prompt", ""),
        "variables": doc.get("variables") or [],
        "temperature": float(doc.get("temperature", 0.4)),
        "example_input": doc.get("example_input"),
        "example_output": doc.get("example_output"),
        "seed_id": doc.get("id"),
    }


def _package_default_config(doc: dict) -> dict:
    return dict(doc.get("default_config") or {})


def _load_prompt_docs() -> list[dict]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    docs = []
    for entry in index["templates"]:
        docs.append(json.loads((SEEDS / entry["file"]).read_text(encoding="utf-8")))
    return docs


def _load_package_docs() -> list[dict]:
    index = json.loads(PACKAGES_INDEX.read_text(encoding="utf-8"))
    docs = []
    for entry in index["templates"]:
        docs.append(json.loads((PACKAGES / entry["file"]).read_text(encoding="utf-8")))
    return docs


def _template_upsert(doc: dict, *, kind: str) -> str:
    if kind == "package":
        cfg = _package_default_config(doc)
        package_path = doc.get("package_path")
        package_path_sql = _sql_str(package_path) if package_path else "NULL"
        thumbnail = doc.get("thumbnail")
        thumbnail_sql = _sql_str(thumbnail) if thumbnail else "NULL"
        supports_agents = _sql_bool(bool(doc.get("supports_agents", True)))
        supports_domains = _sql_bool(bool(doc.get("supports_domains", True)))
        supports_billing = _sql_bool(bool(doc.get("supports_billing", False)))
        supports_mobile = _sql_bool(bool(doc.get("supports_mobile", False)))
    else:
        cfg = _prompt_default_config(doc)
        package_path_sql = "NULL"
        thumbnail_sql = "NULL"
        supports_agents = "TRUE"
        supports_domains = "FALSE"
        supports_billing = "FALSE"
        supports_mobile = "FALSE"

    visibility = (doc.get("visibility") or "public").lower()
    is_public = _sql_bool(visibility == "public")
    featured = _sql_bool(bool(doc.get("featured")))
    status = "published" if visibility == "public" or doc.get("publish") else "draft"
    industry = doc.get("industry")
    industry_sql = _sql_str(industry) if industry else "NULL"
    author = doc.get("author") or "THTWAAT"
    return f"""INSERT INTO marketplace_templates (
  id, slug, name, category, kind, pricing_tier, industry, description, version,
  thumbnail, icon, tags, author, status, price, is_public, is_featured,
  supports_agents, supports_domains, supports_billing, supports_mobile,
  package_path, install_count, default_config, created_at, updated_at
) VALUES (
  {_sql_str(doc['id'])}::uuid,
  {_sql_str(doc['slug'])},
  {_sql_str(doc['name'])},
  {_sql_str(doc['category'])}::template_category_enum,
  {_sql_str(doc.get('kind') or kind)}::template_kind_enum,
  {_sql_str(doc.get('pricing_tier') or 'free')}::template_pricing_tier_enum,
  {industry_sql},
  {_sql_str(doc.get('description') or '')},
  {_sql_str(doc.get('version') or '1.0.0')},
  {thumbnail_sql},
  {_sql_str(doc.get('icon') or ('package' if kind == 'package' else 'sparkles'))},
  {_sql_text_array(list(doc.get('tags') or []))},
  {_sql_str(author)},
  {_sql_str(status)}::template_status_enum,
  0,
  {is_public},
  {featured},
  {supports_agents}, {supports_domains}, {supports_billing}, {supports_mobile},
  {package_path_sql},
  0,
  {_sql_json(cfg)}::jsonb,
  NOW(), NOW()
)
ON CONFLICT (slug) DO UPDATE SET
  name = EXCLUDED.name,
  category = EXCLUDED.category,
  kind = EXCLUDED.kind,
  pricing_tier = EXCLUDED.pricing_tier,
  industry = EXCLUDED.industry,
  description = EXCLUDED.description,
  thumbnail = EXCLUDED.thumbnail,
  icon = EXCLUDED.icon,
  tags = EXCLUDED.tags,
  author = EXCLUDED.author,
  status = EXCLUDED.status,
  is_public = EXCLUDED.is_public,
  is_featured = EXCLUDED.is_featured,
  supports_agents = EXCLUDED.supports_agents,
  supports_domains = EXCLUDED.supports_domains,
  supports_billing = EXCLUDED.supports_billing,
  supports_mobile = EXCLUDED.supports_mobile,
  package_path = EXCLUDED.package_path,
  default_config = EXCLUDED.default_config,
  updated_at = NOW()
  -- note: version column updated only by upgrade script / version insert
;"""


def _version_upsert(doc: dict, *, kind: str, clear_latest: bool) -> str:
    cfg = _package_default_config(doc) if kind == "package" else _prompt_default_config(doc)
    version = doc.get("version") or "1.0.0"
    changelog = doc.get("changelog") or f"Seed {version}"
    tid = _sql_str(doc["id"])
    parts = []
    if clear_latest:
        parts.append(
            f"""UPDATE marketplace_template_versions
SET is_latest = FALSE, updated_at = NOW()
WHERE template_id = {tid}::uuid
  AND version <> {_sql_str(version)}
  AND is_latest = TRUE;"""
        )
    parts.append(
        f"""INSERT INTO marketplace_template_versions (
  id, template_id, version, changelog, config, is_latest, published_at, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  {tid}::uuid,
  {_sql_str(version)},
  {_sql_str(changelog)},
  {_sql_json(cfg)}::jsonb,
  TRUE,
  NOW(),
  NOW(),
  NOW()
)
ON CONFLICT (template_id, version) DO UPDATE SET
  changelog = EXCLUDED.changelog,
  config = EXCLUDED.config,
  is_latest = TRUE,
  published_at = COALESCE(marketplace_template_versions.published_at, NOW()),
  updated_at = NOW();

UPDATE marketplace_templates
SET version = {_sql_str(version)},
    default_config = {_sql_json(cfg)}::jsonb,
    updated_at = NOW()
WHERE id = {tid}::uuid;"""
    )
    return "\n".join(parts)


def _write_catalog(
    *,
    docs: list[dict],
    kind: str,
    seed_path: Path,
    upgrade_path: Path,
    rollback_path: Path,
    stamp: str,
    rollback_note: str,
    cli_hint: str,
) -> None:
    header = f"""-- AUTO-GENERATED by scripts/generate_marketplace_seed_sql.py
-- Generated: {stamp}
-- Templates: {len(docs)} ({kind})
-- Requires migration d0e1f2a3b4c5 (kind, pricing_tier, expanded categories).
-- Idempotent: ON CONFLICT upserts. Safe to re-run.
BEGIN;
"""
    seed_body = [header, f"-- {kind.title()} catalog rows"]
    for doc in docs:
        seed_body.append(_template_upsert(doc, kind=kind))
        seed_body.append(_version_upsert(doc, kind=kind, clear_latest=False))
    seed_body.append("COMMIT;")
    seed_path.write_text("\n".join(seed_body) + "\n", encoding="utf-8")

    upgrade_body = [
        header.replace(
            "Idempotent: ON CONFLICT upserts. Safe to re-run.",
            "Upgrade path: clears prior is_latest, upserts new/current version.",
        ),
        "-- Prefer Python CLI for upgrades in app deploys:",
        f"--   {cli_hint}",
        "-- This SQL mirrors the same version bump semantics for ops.",
    ]
    for doc in docs:
        upgrade_body.append(_template_upsert(doc, kind=kind))
        upgrade_body.append(_version_upsert(doc, kind=kind, clear_latest=True))
    upgrade_body.append("COMMIT;")
    upgrade_path.write_text("\n".join(upgrade_body) + "\n", encoding="utf-8")

    slugs = ",\n  ".join(_sql_str(d["slug"]) for d in docs)
    ids = ",\n  ".join(f"{_sql_str(d['id'])}::uuid" for d in docs)
    rollback = f"""-- AUTO-GENERATED by scripts/generate_marketplace_seed_sql.py
-- Generated: {stamp}
-- {rollback_note}
BEGIN;

DELETE FROM marketplace_template_favorites
WHERE template_id IN (
  {ids}
);

DELETE FROM marketplace_template_installations
WHERE template_id IN (
  {ids}
);

DELETE FROM marketplace_template_versions
WHERE template_id IN (
  {ids}
);

DELETE FROM marketplace_templates
WHERE id IN (
  {ids}
)
   OR slug IN (
  {slugs}
);

COMMIT;
"""
    rollback_path.write_text(rollback, encoding="utf-8")


def main() -> None:
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    prompts = _load_prompt_docs()
    _write_catalog(
        docs=prompts,
        kind="prompt",
        seed_path=SEED_SQL,
        upgrade_path=UPGRADE_SQL,
        rollback_path=ROLLBACK_SQL,
        stamp=stamp,
        rollback_note="Rollback Phase 5 prompt seeds only (does not touch package starters).",
        cli_hint="python -m scripts.seed_marketplace --prompts-only -v",
    )

    packages = _load_package_docs()
    _write_catalog(
        docs=packages,
        kind="package",
        seed_path=PACKAGE_SEED_SQL,
        upgrade_path=PACKAGE_UPGRADE_SQL,
        rollback_path=PACKAGE_ROLLBACK_SQL,
        stamp=stamp,
        rollback_note="Rollback package starter seeds only (does not touch prompt catalog).",
        cli_hint="python -m scripts.seed_marketplace --packages-only -v",
    )

    print(f"Wrote {SEED_SQL.relative_to(ROOT)}")
    print(f"Wrote {UPGRADE_SQL.relative_to(ROOT)}")
    print(f"Wrote {ROLLBACK_SQL.relative_to(ROOT)}")
    print(f"Wrote {PACKAGE_SEED_SQL.relative_to(ROOT)}")
    print(f"Wrote {PACKAGE_UPGRADE_SQL.relative_to(ROOT)}")
    print(f"Wrote {PACKAGE_ROLLBACK_SQL.relative_to(ROOT)}")
    print(f"Prompt templates: {len(prompts)}")
    print(f"Package templates: {len(packages)}")


if __name__ == "__main__":
    main()
