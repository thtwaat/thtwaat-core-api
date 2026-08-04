# Marketplace Store Home v1

Production-shaped storefront on top of the existing **marketplace install engine** + **agent_store** commerce layer. Additive APIs only — no breaking response changes, no third catalog.

## What shipped

- `GET /api/v1/marketplace/home` — named rails + enriched categories + collections
- Collections public + admin CRUD under `/marketplace/collections` and `/marketplace/admin/collections`
- Category meta table (`marketplace_category_meta`) for icons / featured / popularity
- Template enrichment fields (media, trust, ratings bridge, pricing badge)
- SaaS Store Home at `/app/templates` and detail route `/app/templates/[slug]`
- Demo seeds via `seed_store_home()` (also invoked from full catalog seed)

## Migrate + seed

```bash
alembic upgrade head
python -m scripts.seed_marketplace
```

Or call only store-home seeds:

```python
from app.marketplace.seed_store_home import seed_store_home
seed_store_home(db)
```

## Client usage

```ts
const home = await marketplaceApi.home();
const collection = await marketplaceApi.collection("best-for-smb");
const detail = await marketplaceApi.get("ai-saas-starter"); // records a view event
```

Install / favorite / update / rollback paths are unchanged.

## Compatibility

Old clients may ignore new JSON fields. Existing `/marketplace/dashboard`, `/templates`, and install routes remain stable.
