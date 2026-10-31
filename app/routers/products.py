from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product
from app.schemas import ProductCreate, ProductOut, ProductUpdate
from app.security import require_api_key

router = APIRouter(prefix="/products", tags=["products"])


def _get_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")
    return product


@router.get("", response_model=list[ProductOut])
def list_products(
    low_stock: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Product]:
    stmt = select(Product).order_by(Product.id).limit(limit).offset(offset)
    if low_stock:
        stmt = stmt.where(Product.stock <= Product.reorder_level)
    return list(db.scalars(stmt))


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    return _get_or_404(db, product_id)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_product(body: ProductCreate, db: Session = Depends(get_db)) -> Product:
    if db.scalar(select(Product.id).where(Product.sku == body.sku)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"SKU {body.sku} already exists")
    product = Product(**body.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductOut, dependencies=[Depends(require_api_key)])
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    product = _get_or_404(db, product_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_product(product_id: int, db: Session = Depends(get_db)) -> Response:
    product = _get_or_404(db, product_id)
    db.delete(product)
    db.commit()  # IntegrityError (product used in orders) is mapped to 409 in main.py
    return Response(status_code=status.HTTP_204_NO_CONTENT)
