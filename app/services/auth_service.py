from datetime import datetime, timezone
from typing import Optional
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, InactiveUserError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password
)
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.tenant_repo = TenantRepository(db)
        self.user_repo = UserRepository(db)
        self.audit = AuditService(db)

    def login(
        self,
        data: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenResponse:
        """Authenticates a user against a specific tenant using Argon2id."""
        tenant = self.tenant_repo.get_by_slug(data.tenant_slug)
        if not tenant or not tenant.is_active:
            raise AuthenticationError("Invalid tenant credentials or inactive tenant.")

        user = self.user_repo.get_by_email_in_tenant(data.email, tenant.id)
        if not user:
            self.audit.log(
                tenant_id=tenant.id,
                action="AUTH_LOGIN_FAILED",
                resource_type="AUTH",
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "User not found", "email": data.email}
            )
            raise AuthenticationError("Invalid email or password.")

        if not verify_password(data.password, user.hashed_password):
            self.audit.log(
                tenant_id=tenant.id,
                action="AUTH_LOGIN_FAILED",
                resource_type="AUTH",
                resource_id=str(user.id),
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Password mismatch"}
            )
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            self.audit.log(
                tenant_id=tenant.id,
                action="AUTH_LOGIN_FAILED",
                resource_type="AUTH",
                resource_id=str(user.id),
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Account is inactive"}
            )
            raise InactiveUserError("User account has been deactivated.")

        role_names = user.role_names
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(tenant.id),
            roles=role_names
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(tenant.id)
        )

        self.audit.log(
            tenant_id=tenant.id,
            action="AUTH_LOGIN_SUCCESS",
            resource_type="AUTH",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            details={"email": user.email, "roles": role_names}
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    def refresh_access_token(self, refresh_token_str: str) -> TokenResponse:
        """Validates a refresh token and issues a new access/refresh token pair."""
        try:
            payload = decode_token(refresh_token_str)
        except jwt.PyJWTError:
            raise AuthenticationError("Invalid or expired refresh token.")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Token is not a valid refresh token.")

        user_id_str = payload.get("sub")
        tenant_id_str = payload.get("tenant_id")
        if not user_id_str or not tenant_id_str:
            raise AuthenticationError("Malformed token claims.")

        user = self.user_repo.get(user_id_str)
        if not user or str(user.tenant_id) != tenant_id_str or not user.is_active:
            raise AuthenticationError("User is no longer active or valid.")

        role_names = user.role_names
        new_access = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            roles=role_names
        )
        new_refresh = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id)
        )

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
