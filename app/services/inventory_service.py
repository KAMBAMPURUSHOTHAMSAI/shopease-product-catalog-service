from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.core.config import get_settings
from app.schemas.inventory_schema import StockChange


def get_stock(db: Session, product_id: int, admin: bool):
    product = db.get(Product, product_id)
    if not product or (not admin and (not product.is_active or not product.category.is_active)):
        raise HTTPException(404, "Product not found.")
    return {"product_id": product.id, "stock_quantity": product.stock_quantity}


def _replay_idempotent_transaction(db: Session, product_id: int, payload: StockChange, direction: str, key: str):
    prior = db.scalar(select(InventoryTransaction).where(
        InventoryTransaction.idempotency_key == key
    ).with_for_update())
    if prior is None:
        return None
    if prior.product_id != product_id or prior.transaction_type != direction or prior.quantity != payload.quantity:
        raise HTTPException(409, "Idempotency-Key was already used for a different inventory operation.")
    return {
        "product_id": prior.product_id,
        "stock_quantity": prior.updated_stock,
        "transaction": prior,
    }


def change_stock(db: Session, product_id: int, payload: StockChange, direction: str, idempotency_key: str | None = None):
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(422, "Idempotency-Key must contain 1 to 128 characters.")
        replay = _replay_idempotent_transaction(db, product_id, payload, direction, idempotency_key)
        if replay is not None:
            return replay

    # This per-product row lock serializes every inventory mutation for a product.
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(404, "Product not found.")

    # Re-check after acquiring the product lock using a locking/current read.
    # This prevents a duplicate request for this product from applying twice.
    if idempotency_key is not None:
        replay = _replay_idempotent_transaction(db, product_id, payload, direction, idempotency_key)
        if replay is not None:
            return replay

    previous = product.stock_quantity
    updated = previous + payload.quantity if direction == "IN" else previous - payload.quantity
    if updated < 0:
        raise HTTPException(409, "Insufficient stock. Stock quantity cannot become negative.")

    product.stock_quantity = updated
    txn = InventoryTransaction(
        product_id=product.id,
        transaction_type=direction,
        quantity=payload.quantity,
        previous_stock=previous,
        updated_stock=updated,
        remarks=payload.remarks,
        idempotency_key=idempotency_key,
    )
    db.add(txn)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent request using the same key may have committed first.
        if idempotency_key is not None:
            replay = _replay_idempotent_transaction(db, product_id, payload, direction, idempotency_key)
            if replay is not None:
                return replay
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(product)
    db.refresh(txn)
    return {"product_id": product.id, "stock_quantity": product.stock_quantity, "transaction": txn}


def history(db: Session, product_id: int):
    if not db.get(Product, product_id):
        raise HTTPException(404, "Product not found.")
    return list(db.scalars(select(InventoryTransaction).where(
        InventoryTransaction.product_id == product_id
    ).order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())).all())


def low_stock(db: Session, threshold: int | None):
    from app.models.product_model import Product
    from sqlalchemy import select
    limit = get_settings().low_stock_threshold if threshold is None else threshold
    stmt = select(Product).where(Product.is_active.is_(True), Product.stock_quantity <= limit).order_by(Product.stock_quantity, Product.id)
    return [{"product_id": p.id, "name": p.name, "sku": p.sku, "stock_quantity": p.stock_quantity, "threshold": limit} for p in db.scalars(stmt).all()]
