import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models.audit import AuditLog
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditRepository(db)

    def log(
        self,
        tenant_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[AuditLog]:
        if not settings.AUDIT_LOG_ENABLED:
            return None

        try:
            record = self.repo.log_event(
                tenant_id=tenant_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                details=details
            )
            logger.info(
                f"[AUDIT] tenant={tenant_id} action={action} status={status} "
                f"resource={resource_type}:{resource_id} user={user_id}"
            )
            return record
        except Exception as e:
            # Audit failures must be logged to stdout with high priority without crashing application flow
            logger.error(f"[AUDIT_FAILURE] Could not write audit log: {str(e)}")
            return None

    def list_logs(
        self,
        tenant_id: uuid.UUID,
        action: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        return self.repo.list_by_tenant(
            tenant_id=tenant_id,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            skip=skip,
            limit=limit
        )
