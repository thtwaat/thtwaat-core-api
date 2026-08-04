"""CLI: seed marketplace templates into the registry (Phase 5).

Usage:
  python -m scripts.seed_marketplace
  python -m scripts.seed_marketplace --prompts-only
  python -m scripts.seed_marketplace --packages-only
  python -m scripts.seed_marketplace --dry-run
  python -m scripts.seed_marketplace --no-upgrade
  python -m scripts.seed_marketplace --no-refresh

Packages are loaded from data/marketplace/seeds/packages/ (JSON + SQL mirrors).
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent marketplace seed (packages + prompts)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prompts-only", action="store_true", help="Seed JSON prompt catalog only")
    group.add_argument("--packages-only", action="store_true", help="Seed package starters only")
    parser.add_argument("--dry-run", action="store_true", help="Plan actions without writing")
    parser.add_argument(
        "--no-upgrade",
        action="store_true",
        help="Skip version bumps when seed version differs",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Do not refresh metadata when seed version matches",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print per-slug actions")
    args = parser.parse_args()

    # CLI does not load main.py — register Company/User/etc. before any Session.
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.database.database import SessionLocal
    from app.marketplace.seed import seed_marketplace_catalog

    include_packages = not args.prompts_only
    include_prompts = not args.packages_only

    db = SessionLocal()
    try:
        stats = seed_marketplace_catalog(
            db,
            include_packages=include_packages,
            include_prompts=include_prompts,
            upgrade=not args.no_upgrade,
            refresh_same_version=not args.no_refresh,
            dry_run=args.dry_run,
        )
        prefix = "[dry-run] " if args.dry_run else ""
        print(
            f"{prefix}Marketplace seed: created={stats.created} "
            f"upgraded={stats.upgraded} updated={stats.updated} skipped={stats.skipped}"
        )
        if args.verbose:
            for slug, action in stats.actions:
                print(f"  {action:9} {slug}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
