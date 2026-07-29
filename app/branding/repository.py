"""Repository for company branding and assets."""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.branding.models import BrandingAsset, BrandingAssetType, CompanyBranding


class BrandingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_company(self, company_id: uuid.UUID) -> Optional[CompanyBranding]:
        return self.db.scalar(
            select(CompanyBranding).where(CompanyBranding.company_id == company_id)
        )

    def create(self, row: CompanyBranding) -> CompanyBranding:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: CompanyBranding) -> CompanyBranding:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_assets(
        self, company_id: uuid.UUID, active_only: bool = True
    ) -> List[BrandingAsset]:
        stmt = select(BrandingAsset).where(BrandingAsset.company_id == company_id)
        if active_only:
            stmt = stmt.where(BrandingAsset.is_active.is_(True))
        stmt = stmt.order_by(BrandingAsset.asset_type, BrandingAsset.version.desc())
        return list(self.db.scalars(stmt).all())

    def next_asset_version(self, company_id: uuid.UUID, asset_type: BrandingAssetType) -> int:
        rows = self.db.scalars(
            select(BrandingAsset.version)
            .where(
                BrandingAsset.company_id == company_id,
                BrandingAsset.asset_type == asset_type,
            )
            .order_by(BrandingAsset.version.desc())
            .limit(1)
        ).all()
        return (rows[0] if rows else 0) + 1

    def deactivate_active_assets(self, company_id: uuid.UUID, asset_type: BrandingAssetType) -> None:
        self.db.execute(
            update(BrandingAsset)
            .where(
                BrandingAsset.company_id == company_id,
                BrandingAsset.asset_type == asset_type,
                BrandingAsset.is_active.is_(True),
            )
            .values(is_active=False)
        )

    def add_asset(self, asset: BrandingAsset) -> BrandingAsset:
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def delete_all_for_company(self, company_id: uuid.UUID) -> None:
        row = self.get_by_company(company_id)
        if row:
            self.db.delete(row)
            self.db.commit()
