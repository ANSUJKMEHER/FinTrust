from typing import Optional


class FinTrustBaseException(Exception):
    """Base exception for all FinTrust domain errors."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(FinTrustBaseException):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""
    pass


class InactiveUserError(FinTrustBaseException):
    """Raised when an inactive user attempts to log in or access resources."""
    pass


class PermissionDeniedError(FinTrustBaseException):
    """Raised when an authenticated user attempts an operation outside their authorized role/permissions."""
    pass


class TenantAccessViolationError(FinTrustBaseException):
    """Raised when a cross-tenant resource access attempt is detected."""
    pass


class EntityNotFoundError(FinTrustBaseException):
    """Raised when a requested resource is not found."""
    pass


class EntityAlreadyExistsError(FinTrustBaseException):
    """Raised when an entity with duplicate unique constraints is created."""
    pass


class ValidationError(FinTrustBaseException):
    """Raised when domain input validation fails."""
    pass


class DocumentAccessDeniedError(PermissionDeniedError):
    """Raised when access to a specific document is rejected by ACL rules."""
    pass
