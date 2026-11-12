from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.core.config import get_settings
from app.schemas.inventory_schema import StockChange
from app.services.common import commit_or_raise

def get_stock(db: Session, product_id: int, admin: bool):
    product = db.get(Product, product_id)
    if not product or (not admin and (not product.is_active or not product.category.is_active)):
        raise HTTPException(404, "Product not found.")
    return {"product_id": product.id, "stock_quantity": product.stock_quantity}

def change_stock(db: Session, product_id: int, payload: StockChange, direction: str):
    # In MySQL/InnoDB, SELECT ... FOR UPDATE serializes concurrent stock changes on this product row.
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product: raise HTTPException(404, "Product not found.")
    previous = product.stock_quantity
    updated = previous + payload.quantity if direction == "IN" else previous - payload.quantity
    if updated < 0: raise HTTPException(409, "Insufficient stock. Stock quantity cannot become negative.")
    product.stock_quantity = updated
    txn = InventoryTransaction(product_id=product.id, transaction_type=direction, quantity=payload.quantity,
        previous_stock=previous, updated_stock=updated, remarks=payload.remarks)
    db.add(txn)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(product); db.refresh(txn)
    return {"product_id": product.id, "stock_quantity": product.stock_quantity, "transaction": txn}

def history(db: Session, product_id: int):
    if not db.get(Product, product_id): raise HTTPException(404, "Product not found.")
    return list(db.scalars(select(InventoryTransaction).where(InventoryTransaction.product_id == product_id).order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())).all())

def low_stock(db: Session, threshold: int | None):
    limit = get_settings().low_stock_threshold if threshold is None else threshold
    stmt = select(Product).where(Product.is_active.is_(True), Product.stock_quantity <= limit).order_by(Product.stock_quantity, Product.id)
    return [{"product_id": p.id, "name": p.name, "sku": p.sku, "stock_quantity": p.stock_quantity, "threshold": limit} for p in db.scalars(stmt).all()]
