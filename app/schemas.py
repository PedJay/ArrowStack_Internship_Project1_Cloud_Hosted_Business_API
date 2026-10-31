from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

SKU_PATTERN = r"^[A-Z0-9-]{3,32}$"
EMAIL_PATTERN = r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$"


class ProductCreate(BaseModel):
    sku: str = Field(pattern=SKU_PATTERN, examples=["TSHIRT-BLK-M"])
    name: str = Field(min_length=1, max_length=120)
    price_cents: int = Field(ge=0, le=10_000_000, description="Price in the smallest currency unit")
    stock: int = Field(default=0, ge=0, le=1_000_000)
    reorder_level: int = Field(default=5, ge=0, le=1_000_000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    price_cents: int
    stock: int
    reorder_level: int
    low_stock: bool
    created_at: datetime
    updated_at: datetime


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=1000)


class OrderCreate(BaseModel):
    customer_email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def _unique_products(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        ids = [i.product_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("each product may appear only once per order")
        return items


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int
    unit_price_cents: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_email: str
    status: str
    total_cents: int
    created_at: datetime
    items: list[OrderItemOut]
