from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

def commit_or_raise(db, message: str = "The request conflicts with existing data."):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=message) from exc
    except Exception:
        db.rollback()
        raise
