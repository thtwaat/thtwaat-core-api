"""Unit tests for Studio schemas and delete permission (no DB)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.studio.schemas import StudioProjectCreate
from app.studio.service import derive_title


@pytest.mark.unit
def test_studio_create_schema_validates_prompt():
    ok = StudioProjectCreate(prompt="Create a CRM with leads and invoices")
    assert "CRM" in ok.prompt

    with pytest.raises(ValidationError):
        StudioProjectCreate(prompt="short")


@pytest.mark.unit
def test_derive_title_unit():
    assert derive_title("Create a CRM\nwith billing") == "Create a CRM"
    assert derive_title("x" * 100).endswith("...")
    assert derive_title("prompt", "Named") == "Named"
