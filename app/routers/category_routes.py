from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.core.security import AuthenticatedUser, get_current_user, require_admin
from app.database.connection import get_db
from app.schemas.category_schema import CategoryCreate, CategoryUpdate, CategoryOut
from app.services import category_service
router = APIRouter(prefix="/api/categories", tags=["Categories"])

@router.post("/", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return category_service.create_category(db, payload)

@router.get("/", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    return category_service.list_categories(db, user.role in {"admin","administrator","super_admin"})

@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    return category_service.get_category(db, category_id, user.role in {"admin","administrator","super_admin"})

@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    return category_service.update_category(db, category_id, payload)

@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)):
    category_service.delete_category(db, category_id); return Response(status_code=204)
