import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.role import Role
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_id_and_tenant(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[User]:
        return self.db.query(User).filter(
            User.id == user_id,
            User.tenant_id == tenant_id
        ).first()

    def get_by_email_in_tenant(self, email: str, tenant_id: uuid.UUID) -> Optional[User]:
        return self.db.query(User).filter(
            User.email == email,
            User.tenant_id == tenant_id
        ).first()

    def list_by_tenant(self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).filter(
            User.tenant_id == tenant_id
        ).offset(skip).limit(limit).all()

    def get_roles_by_names(self, role_names: List[str]) -> List[Role]:
        return self.db.query(Role).filter(Role.id.in_(role_names)).all()
