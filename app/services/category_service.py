from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.category_model import Category
from app.models.product_model import Product
from app.schemas.category_schema import CategoryCreate, CategoryUpdate
from app.services.common import commit_or_raise

def create_category(db: Session, payload: CategoryCreate):
    if db.scalar(select(Category).where(Category.name == payload.name)):
        raise HTTPException(409, "A category with this name already exists.")
    obj = Category(**payload.model_dump())
    db.add(obj); commit_or_raise(db, "Category name already exists."); db.refresh(obj)
    return obj

def list_categories(db: Session, admin: bool):
    stmt = select(Category).order_by(Category.name)
    if not admin: stmt = stmt.where(Category.is_active.is_(True))
    return list(db.scalars(stmt).all())

def get_category(db: Session, category_id: int, admin: bool):
    obj = db.get(Category, category_id)
    if not obj or (not admin and not obj.is_active): raise HTTPException(404, "Category not found.")
    return obj

def update_category(db: Session, category_id: int, payload: CategoryUpdate):
    obj = db.get(Category, category_id)
    if not obj: raise HTTPException(404, "Category not found.")
    data = payload.model_dump()
    duplicate = db.scalar(select(Category).where(Category.name == data["name"], Category.id != category_id))
    if duplicate: raise HTTPException(409, "A category with this name already exists.")
    for key, value in data.items(): setattr(obj, key, value)
    commit_or_raise(db, "Category name already exists."); db.refresh(obj); return obj

def delete_category(db: Session, category_id: int):
    obj = db.get(Category, category_id)
    if not obj: raise HTTPException(404, "Category not found.")
    if db.scalar(select(Product.id).where(Product.category_id == category_id).limit(1)):
        raise HTTPException(409, "Category contains products. Reassign or deactivate products before deleting it.")
    db.delete(obj); commit_or_raise(db); return
