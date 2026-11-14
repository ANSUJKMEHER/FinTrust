import uuid
from typing import Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, InactiveUserError, PermissionDeniedError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Extracts, decodes, and verifies the JWT token and binds the authenticated User context."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        tenant_id_str: str = payload.get("tenant_id")
        token_type: str = payload.get("type")
        
        if not user_id_str or not tenant_id_str or token_type != "access":
            raise credentials_exception
            
        user_id = uuid.UUID(user_id_str)
        tenant_id = uuid.UUID(tenant_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Factory dependency that verifies the user possesses at least one of the allowed roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = current_user.role_names
        if "ADMIN" in user_roles:
            # ADMIN has tenant-wide superset access
            return current_user
            
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of the following roles: {list(allowed_roles)}"
            )
        return current_user

    return role_checker


def get_current_active_admin(
    current_user: User = Depends(require_roles("ADMIN"))
) -> User:
    """Dependency that guarantees the caller is an active tenant Administrator."""
    return current_user
