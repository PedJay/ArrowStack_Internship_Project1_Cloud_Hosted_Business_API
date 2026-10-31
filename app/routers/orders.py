import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Order, OrderItem, Product
from app.schemas import OrderCreate, OrderOut
from app.security import require_api_key

router = APIRouter(prefix="/orders", tags=["orders"])
log = logging.getLogger("app.orders")


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_order(body: OrderCreate, db: Session = Depends(get_db)) -> Order:
    wanted = {item.product_id: item.quantity for item in body.items}

    # Lock the product rows (Postgres: SELECT ... FOR UPDATE) in a fixed order so two
    # concurrent orders for the same product can't both pass the stock check or deadlock.
    stmt = select(Product).where(Product.id.in_(wanted)).order_by(Product.id).with_for_update()
    products = {p.id: p for p in db.scalars(stmt)}

    missing = sorted(set(wanted) - set(products))
    if missing:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"error": "unknown_products", "product_ids": missing})

    short = [
        {"product_id": pid, "requested": qty, "available": products[pid].stock}
        for pid, qty in wanted.items()
        if products[pid].stock < qty
    ]
    if short:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"error": "insufficient_stock", "items": short})

    order = Order(customer_email=body.customer_email.lower(), total_cents=0)
    total = 0
    for pid, qty in wanted.items():
        product = products[pid]
        product.stock -= qty
        total += product.price_cents * qty
        order.items.append(OrderItem(product_id=pid, quantity=qty, unit_price_cents=product.price_cents))
    order.total_cents = total

    db.add(order)
    db.commit()
    db.refresh(order)
    log.info("order created", extra={"extra_fields": {"order_id": order.id, "total_cents": total, "lines": len(wanted)}})
    return order


@router.get("", response_model=list[OrderOut])
def list_orders(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Order]:
    stmt = select(Order).options(selectinload(Order.items)).order_by(Order.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)) -> Order:
    order = db.get(Order, order_id, options=[selectinload(Order.items)])
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found")
    return order
