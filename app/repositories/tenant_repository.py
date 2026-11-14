import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.tenant import Tenant
from app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, db: Session):
        super().__init__(Tenant, db)

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.slug == slug).first()

    def get_by_id(self, tenant_id: uuid.UUID) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def list_active(self, skip: int = 0, limit: int = 100) -> List[Tenant]:
        return self.db.query(Tenant).filter(Tenant.is_active == True).offset(skip).limit(limit).all()
