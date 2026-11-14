import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, model_validator


class PermissionGrant(BaseModel):
    role_id: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    can_read: bool = True
    can_write: bool = False

    @model_validator(mode="after")
    def validate_target(self) -> "PermissionGrant":
        if not self.role_id and not self.user_id:
            raise ValueError("Either role_id or user_id must be provided for permission grant.")
        if self.role_id and self.user_id:
            raise ValueError("Specify either role_id or user_id, not both in a single rule.")
        return self


class PermissionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    tenant_id: uuid.UUID
    role_id: Optional[str]
    user_id: Optional[uuid.UUID]
    can_read: bool
    can_write: bool
    created_at: datetime

    model_config = {"from_attributes": True}
