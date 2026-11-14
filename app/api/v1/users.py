import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_admin, get_current_user, require_roles
from app.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError, PermissionDeniedError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    current_admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
) -> UserResponse:
    user_service = UserService(db)
    try:
        user = user_service.create_user(
            tenant_id=current_admin.tenant_id,
            data=data,
            creator=current_admin
        )
        return UserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=user.role_names,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except EntityAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_roles("ADMIN", "COMPLIANCE_OFFICER")),
    db: Session = Depends(get_db)
) -> List[UserResponse]:
    user_service = UserService(db)
    users = user_service.list_users(current_user.tenant_id, skip=skip, limit=limit)
    return [
        UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            roles=u.role_names,
            created_at=u.created_at,
            updated_at=u.updated_at
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    user_service = UserService(db)
    try:
        u = user_service.get_user_by_id(user_id, current_user.tenant_id)
        return UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            roles=u.role_names,
            created_at=u.created_at,
            updated_at=u.updated_at
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    user_service = UserService(db)
    try:
        u = user_service.update_user(user_id, current_user.tenant_id, data, current_user)
        return UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            roles=u.role_names,
            created_at=u.created_at,
            updated_at=u.updated_at
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
