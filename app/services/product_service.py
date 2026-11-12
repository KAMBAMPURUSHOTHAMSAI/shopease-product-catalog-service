from math import ceil
from fastapi import HTTPException
from sqlalchemy import select, func, or_, asc, desc
from sqlalchemy.orm import Session
from app.models.category_model import Category
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.schemas.product_schema import ProductCreate, ProductUpdate, ProductPatch
from app.services.common import commit_or_raise

SORT_COLUMNS = {"name": Product.name, "price": Product.price, "created_at": Product.created_at, "stock_quantity": Product.stock_quantity, "updated_at": Product.updated_at}

def ensure_category(db, category_id, allow_inactive=False):
    category = db.get(Category, category_id)
    if not category or (not allow_inactive and not category.is_active): raise HTTPException(404, "Active category not found.")
    return category

def _record_initial_stock(db, product):
    if product.stock_quantity > 0:
        db.add(InventoryTransaction(product_id=product.id, transaction_type="IN", quantity=product.stock_quantity,
            previous_stock=0, updated_stock=product.stock_quantity, remarks="Opening stock at product creation"))

def create_product(db: Session, payload: ProductCreate):
    ensure_category(db, payload.category_id)
    if db.scalar(select(Product.id).where(Product.sku == payload.sku)):
        raise HTTPException(409, "A product with this SKU already exists.")
    obj = Product(**payload.model_dump()); db.add(obj); db.flush()
    _record_initial_stock(db, obj)
    commit_or_raise(db, "Product SKU already exists."); db.refresh(obj); return obj

def list_products(db: Session, admin: bool, search=None, category_id=None, min_price=None, max_price=None, available=None,
                  page=1, page_size=10, sort_by="created_at", sort_order="desc"):
    stmt = select(Product).join(Category, Product.category_id == Category.id)
    count_stmt = select(func.count(Product.id)).join(Category, Product.category_id == Category.id)
    if not admin:
        stmt = stmt.where(Product.is_active.is_(True), Category.is_active.is_(True))
        count_stmt = count_stmt.where(Product.is_active.is_(True), Category.is_active.is_(True))
    if search:
        cond = or_(Product.name.ilike(f"%{search}%"), Product.sku.ilike(f"%{search}%"))
        stmt, count_stmt = stmt.where(cond), count_stmt.where(cond)
    if category_id is not None:
        stmt, count_stmt = stmt.where(Product.category_id == category_id), count_stmt.where(Product.category_id == category_id)
    if min_price is not None:
        stmt, count_stmt = stmt.where(Product.price >= min_price), count_stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt, count_stmt = stmt.where(Product.price <= max_price), count_stmt.where(Product.price <= max_price)
    if available is True:
        stmt, count_stmt = stmt.where(Product.stock_quantity > 0), count_stmt.where(Product.stock_quantity > 0)
    elif available is False:
        stmt, count_stmt = stmt.where(Product.stock_quantity == 0), count_stmt.where(Product.stock_quantity == 0)
    total = db.scalar(count_stmt) or 0
    column = SORT_COLUMNS[sort_by]
    stmt = stmt.order_by(asc(column) if sort_order == "asc" else desc(column), Product.id.asc()).offset((page-1)*page_size).limit(page_size)
    items = list(db.scalars(stmt).all())
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": ceil(total/page_size) if total else 0}

def get_product(db: Session, product_id: int, admin: bool):
    obj = db.get(Product, product_id)
    if not obj: raise HTTPException(404, "Product not found.")
    if not admin and (not obj.is_active or not obj.category.is_active): raise HTTPException(404, "Product not found.")
    return obj

def _validate_discount(price, discount):
    if discount is not None and (discount <= 0 or discount >= price): raise HTTPException(422, "discount_price must be greater than zero and less than price.")

def update_product(db: Session, product_id: int, payload: ProductUpdate):
    obj = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not obj: raise HTTPException(404, "Product not found.")
    data = payload.model_dump()
    ensure_category(db, data["category_id"])
    duplicate = db.scalar(select(Product.id).where(Product.sku == data["sku"], Product.id != product_id))
    if duplicate: raise HTTPException(409, "A product with this SKU already exists.")
    _validate_discount(data["price"], data["discount_price"])
    old_stock = obj.stock_quantity
    for key, value in data.items():
        if key != "stock_quantity": setattr(obj, key, value)
    if data["stock_quantity"] != old_stock:
        new_stock = data["stock_quantity"]
        db.add(InventoryTransaction(product_id=obj.id, transaction_type="IN" if new_stock > old_stock else "OUT",
            quantity=abs(new_stock-old_stock), previous_stock=old_stock, updated_stock=new_stock, remarks="Stock adjusted through product update"))
        obj.stock_quantity = new_stock
    commit_or_raise(db, "Product SKU already exists or product data conflicts."); db.refresh(obj); return obj

def patch_product(db: Session, product_id: int, payload: ProductPatch):
    obj = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not obj: raise HTTPException(404, "Product not found.")
    data = payload.model_dump(exclude_unset=True)
    if not data: raise HTTPException(422, "At least one field must be provided.")
    if "category_id" in data: ensure_category(db, data["category_id"])
    if "sku" in data:
        duplicate = db.scalar(select(Product.id).where(Product.sku == data["sku"], Product.id != product_id))
        if duplicate: raise HTTPException(409, "A product with this SKU already exists.")
    new_price = data.get("price", obj.price)
    new_discount = data.get("discount_price", obj.discount_price)
    _validate_discount(new_price, new_discount)
    if "stock_quantity" in data:
        old, new = obj.stock_quantity, data["stock_quantity"]
        if new is None or new < 0: raise HTTPException(422, "Stock quantity cannot be negative.")
        if new != old:
            db.add(InventoryTransaction(product_id=obj.id, transaction_type="IN" if new > old else "OUT", quantity=abs(new-old), previous_stock=old, updated_stock=new, remarks="Stock adjusted through product patch"))
    for key, value in data.items(): setattr(obj, key, value)
    commit_or_raise(db, "Product SKU already exists or product data conflicts."); db.refresh(obj); return obj

def delete_product(db: Session, product_id: int):
    obj = db.get(Product, product_id)
    if not obj: raise HTTPException(404, "Product not found.")
    if db.scalar(select(InventoryTransaction.id).where(InventoryTransaction.product_id == product_id).limit(1)):
        raise HTTPException(409, "Product has inventory history. Deactivate it instead to preserve the audit trail.")
    db.delete(obj); commit_or_raise(db); return
