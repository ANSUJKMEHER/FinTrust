import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from app.db.session import get_db
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db)
) -> TenantResponse:
    tenant_service = TenantService(db)
    try:
        tenant = tenant_service.create_tenant(data)
        return tenant
    except EntityAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/", response_model=List[TenantResponse])
def list_tenants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[TenantResponse]:
    tenant_service = TenantService(db)
    return tenant_service.list_tenants(skip=skip, limit=limit)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> TenantResponse:
    tenant_service = TenantService(db)
    try:
        return tenant_service.get_tenant_by_id(tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
