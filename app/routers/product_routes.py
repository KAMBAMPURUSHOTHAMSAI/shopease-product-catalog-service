from decimal import Decimal
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.core.security import AuthenticatedUser, get_current_user, require_admin
from app.database.connection import get_db
from app.schemas.product_schema import ProductCreate, ProductUpdate, ProductPatch, ProductOut, ProductListOut
from app.services import product_service
router = APIRouter(prefix="/api/products", tags=["Products"])

@router.post("/", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return product_service.create_product(db, payload)

@router.get("/", response_model=ProductListOut)
def list_products(search: str | None = Query(default=None, max_length=100), category_id: int | None = Query(default=None, gt=0),
    min_price: Decimal | None = Query(default=None, gt=0), max_price: Decimal | None = Query(default=None, gt=0),
    available: bool | None = None, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(name|price|created_at|stock_quantity|updated_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"), db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    if min_price is not None and max_price is not None and min_price > max_price:
        from fastapi import HTTPException
        raise HTTPException(422, "min_price cannot be greater than max_price.")
    return product_service.list_products(db, user.role in {"admin","administrator","super_admin"}, search, category_id, min_price, max_price, available, page, page_size, sort_by, sort_order)

@router.get("/{product_id}", response_model=ProductOut)
def retrieve_product(product_id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    return product_service.get_product(db, product_id, user.role in {"admin","administrator","super_admin"})

@router.put("/{product_id}", response_model=ProductOut)
def replace_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return product_service.update_product(db, product_id, payload)

@router.patch("/{product_id}", response_model=ProductOut)
def partial_update_product(product_id: int, payload: ProductPatch, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return product_service.patch_product(db, product_id, payload)

@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    product_service.delete_product(db, product_id); return Response(status_code=204)
