"""
app/products/repository.py

Database operations for Products module.
"""
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.products.model import Product

class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, product_id: uuid.UUID, company_id: uuid.UUID) -> Optional[Product]:
        return self.db.execute(
            select(Product).where(Product.id == product_id, Product.company_id == company_id)
        ).scalar_one_or_none()

    def get_by_slug(self, slug: str, company_id: uuid.UUID) -> Optional[Product]:
        return self.db.execute(
            select(Product).where(Product.slug == slug, Product.company_id == company_id)
        ).scalar_one_or_none()

    def list_by_company(self, company_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Product]:
        stmt = select(Product).where(Product.company_id == company_id).order_by(Product.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, product: Product) -> Product:
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update(self, product: Product) -> Product:
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product: Product) -> None:
        self.db.delete(product)
        self.db.commit()
