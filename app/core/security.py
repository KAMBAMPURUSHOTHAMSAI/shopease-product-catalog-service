from dataclasses import dataclass
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="ShopEaseBearer")

@dataclass(frozen=True)
class AuthenticatedUser:
    auth_user_id: int
    role: str


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token.", headers={"WWW-Authenticate": "Bearer"})
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm], issuer=settings.jwt_issuer,
            options={"require": ["exp", "iss", "sub"]})
        subject = str(payload.get("sub", ""))
        role = payload.get("role", "customer")
        if not subject.isdigit() or int(subject) <= 0 or not isinstance(role, str) or not role.strip():
            raise jwt.InvalidTokenError("Invalid subject or role claim")
        return AuthenticatedUser(auth_user_id=int(subject), role=role.strip().lower())
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Authentication token has expired.", headers={"WWW-Authenticate": "Bearer"}) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token.", headers={"WWW-Authenticate": "Bearer"}) from exc


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role not in {"admin", "administrator", "super_admin"}:
        raise HTTPException(status_code=403, detail="Administrator role is required.")
    return user
