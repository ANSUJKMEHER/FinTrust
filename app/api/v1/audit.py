import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("/", response_model=List[AuditLogResponse])
def list_audit_logs(
    action: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles("ADMIN", "COMPLIANCE_OFFICER", "AUDITOR")),
    db: Session = Depends(get_db)
) -> List[AuditLogResponse]:
    audit_service = AuditService(db)
    return audit_service.list_logs(
        tenant_id=current_user.tenant_id,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        skip=skip,
        limit=limit
    )
