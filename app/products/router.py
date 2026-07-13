"""
app/products/router.py

FastAPI router for Products module.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.products.service import ProductService
from app.products.schema import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(
    prefix="/products",
    tags=["Products"],
)

def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(db)

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Create a new Product")
def create_product(
    payload: ProductCreate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    return service.create_product(company_id=current_user.company_id, payload=payload)

@router.get("/", response_model=List[ProductResponse], summary="List Products for Company")
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    return service.list_products(company_id=current_user.company_id, skip=skip, limit=limit)

@router.get("/{product_id}", response_model=ProductResponse, summary="Get Product Details")
def get_product(
    product_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    return service.get_product(company_id=current_user.company_id, product_id=product_id)

@router.patch("/{product_id}", response_model=ProductResponse, summary="Update Product")
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    return service.update_product(company_id=current_user.company_id, product_id=product_id, payload=payload)

@router.delete("/{product_id}", status_code=status.HTTP_200_OK, summary="Delete Product")
def delete_product(
    product_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    service.delete_product(company_id=current_user.company_id, product_id=product_id)
    return {"message": "Product deleted successfully"}
