"""Phase 4: prompt seed catalog integrity."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEEDS = ROOT / "data" / "marketplace" / "seeds"
INDEX = SEEDS / "index.json"
PROMPTS = SEEDS / "prompts"

REQUIRED = {
    "id",
    "slug",
    "name",
    "description",
    "category",
    "kind",
    "prompt",
    "variables",
    "temperature",
    "tags",
    "visibility",
    "featured",
    "version",
    "example_input",
    "example_output",
    "pricing_tier",
}


def test_prompt_seed_catalog_has_100_valid_templates():
    assert INDEX.exists(), "missing data/marketplace/seeds/index.json — run generate script"
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert index["count"] == 100
    files = sorted(PROMPTS.glob("*.json"))
    assert len(files) == 100

    slugs = set()
    ids = set()
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        missing = REQUIRED - set(doc)
        assert not missing, f"{path.name} missing {missing}"
        assert doc["visibility"] == "public"
        assert doc["kind"] in {"prompt", "agent"}
        assert 0 <= float(doc["temperature"]) <= 1
        assert isinstance(doc["variables"], list) and doc["variables"]
        assert doc["slug"] not in slugs
        assert doc["id"] not in ids
        slugs.add(doc["slug"])
        ids.add(doc["id"])

    assert len(index["templates"]) == 100
    assert set(t["slug"] for t in index["templates"]) == slugs
