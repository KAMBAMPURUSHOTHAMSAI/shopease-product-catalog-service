from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from app.core.security import AuthenticatedUser, get_current_user, require_admin
from app.database.connection import get_db
from app.schemas.inventory_schema import StockChange, InventoryOut, InventoryTransactionOut, LowStockProduct
from app.services import inventory_service

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])

@router.get("/low-stock", response_model=list[LowStockProduct])
def low_stock(threshold: int | None = Query(default=None, ge=0), db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return inventory_service.low_stock(db, threshold)

@router.get("/{product_id}", response_model=InventoryOut)
def get_stock(product_id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    return inventory_service.get_stock(db, product_id, user.role in {"admin", "administrator", "super_admin"})

@router.post("/{product_id}/stock-in")
def stock_in(
    product_id: int,
    payload: StockChange,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
):
    return inventory_service.change_stock(db, product_id, payload, "IN", idempotency_key)

@router.post("/{product_id}/stock-out")
def stock_out(
    product_id: int,
    payload: StockChange,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
):
    return inventory_service.change_stock(db, product_id, payload, "OUT", idempotency_key)

@router.get("/{product_id}/history", response_model=list[InventoryTransactionOut])
def inventory_history(product_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return inventory_service.history(db, product_id)
