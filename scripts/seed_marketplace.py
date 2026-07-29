"""CLI: seed marketplace templates into the registry.

Usage:
  python -m scripts.seed_marketplace
"""
from __future__ import annotations

from app.database.database import SessionLocal
from app.marketplace.seed import seed_marketplace_templates


def main() -> None:
    db = SessionLocal()
    try:
        created = seed_marketplace_templates(db)
        print(f"Seeded {created} marketplace template(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
