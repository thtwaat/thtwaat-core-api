"""
app/products/service.py

Business logic for Products module.
"""
import uuid
import re
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.products.repository import ProductRepository
from app.products.model import Product
from app.products.schema import ProductCreate, ProductUpdate

class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProductRepository(db)

    def _generate_slug(self, name: str) -> str:
        # Convert to lowercase and replace non-alphanumeric with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return slug

    def create_product(self, company_id: uuid.UUID, payload: ProductCreate) -> Product:
        slug = payload.slug or self._generate_slug(payload.name)
        
        # Ensure slug is unique per company
        existing = self.repo.get_by_slug(slug, company_id)
        if existing:
            # Append short uuid to make unique
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
            
        product = Product(
            company_id=company_id,
            app_id=payload.app_id,
            name=payload.name,
            slug=slug,
            category=payload.category,
            description=payload.description,
            icon=payload.icon,
            version=payload.version,
            ai_enabled=payload.ai_enabled,
            storage_enabled=payload.storage_enabled,
            payment_enabled=payload.payment_enabled,
            notification_enabled=payload.notification_enabled,
            settings=payload.settings,
            metadata_=payload.metadata_
        )
        return self.repo.create(product)

    def get_product(self, company_id: uuid.UUID, product_id: uuid.UUID) -> Product:
        product = self.repo.get_by_id(product_id, company_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    def list_products(self, company_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Product]:
        return self.repo.list_by_company(company_id, skip, limit)

    def update_product(self, company_id: uuid.UUID, product_id: uuid.UUID, payload: ProductUpdate) -> Product:
        product = self.get_product(company_id, product_id)
        
        update_data = payload.model_dump(exclude_unset=True)
        
        if "slug" in update_data and update_data["slug"] != product.slug:
            existing = self.repo.get_by_slug(update_data["slug"], company_id)
            if existing and existing.id != product.id:
                raise HTTPException(status_code=400, detail="Slug already in use by another product")
        elif "name" in update_data and "slug" not in update_data:
            # Auto update slug if name changes and slug isn't explicitly provided
            new_slug = self._generate_slug(update_data["name"])
            existing = self.repo.get_by_slug(new_slug, company_id)
            if not existing or existing.id == product.id:
                update_data["slug"] = new_slug
        
        for key, value in update_data.items():
            setattr(product, key, value)
            
        return self.repo.update(product)

    def delete_product(self, company_id: uuid.UUID, product_id: uuid.UUID) -> None:
        product = self.get_product(company_id, product_id)
        self.repo.delete(product)
