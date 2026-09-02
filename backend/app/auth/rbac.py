"""
Role-Based Access Control (RBAC) for MedSafe

PATTERN: Authorization with hierarchical roles
SKILLS: @api-design-principles, @secrets-management, @ultrathink

SECURITY FIX: Implementação real de verificação de roles no banco de dados
FASE 1.2: Audit logging integration
"""

import logging
from enum import Enum
from typing import List

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..utils.audit_logger import audit_logger
from .jwt import get_current_user

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """
    User roles with hierarchical permissions

    Hierarchy: ADMIN > PHYSICIAN > PHARMACIST > READONLY
    """

    ADMIN = "admin"  # Full system access + user management
    PHYSICIAN = "physician"  # Can create/approve analyses, HITL decisions
    PHARMACIST = "pharmacist"  # Can create triages and review HITL analyses
    READONLY = "readonly"  # Can only view existing analyses (auditor, researcher)


# Role hierarchy mapping (higher roles inherit lower role permissions)
ROLE_HIERARCHY = {
    UserRole.ADMIN: [
        UserRole.ADMIN,
        UserRole.PHYSICIAN,
        UserRole.PHARMACIST,
        UserRole.READONLY,
    ],
    UserRole.PHYSICIAN: [UserRole.PHYSICIAN, UserRole.PHARMACIST, UserRole.READONLY],
    UserRole.PHARMACIST: [UserRole.PHARMACIST, UserRole.READONLY],
    UserRole.READONLY: [UserRole.READONLY],
}


class Permission(str, Enum):
    """Granular permissions for RBAC"""

    # Triage permissions
    TRIAGE_CREATE = "triage:create"
    TRIAGE_READ = "triage:read"
    TRIAGE_UPDATE = "triage:update"
    TRIAGE_DELETE = "triage:delete"

    # Analysis permissions
    ANALYSIS_CREATE = "analysis:create"
    ANALYSIS_READ = "analysis:read"
    ANALYSIS_APPROVE = "analysis:approve"  # HITL approval
    ANALYSIS_REJECT = "analysis:reject"

    # Report permissions
    REPORT_READ = "report:read"
    REPORT_EXPORT = "report:export"

    # User management (admin only)
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # System configuration (admin only)
    CONFIG_UPDATE = "config:update"
    METRICS_VIEW = "metrics:view"
    CACHE_CLEAR = "cache:clear"


# Role-to-Permissions mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        # All triage permissions
        Permission.TRIAGE_CREATE,
        Permission.TRIAGE_READ,
        Permission.TRIAGE_UPDATE,
        Permission.TRIAGE_DELETE,
        # All analysis permissions
        Permission.ANALYSIS_CREATE,
        Permission.ANALYSIS_READ,
        Permission.ANALYSIS_APPROVE,
        Permission.ANALYSIS_REJECT,
        # All report permissions
        Permission.REPORT_READ,
        Permission.REPORT_EXPORT,
        # User management
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        # System config
        Permission.CONFIG_UPDATE,
        Permission.METRICS_VIEW,
        Permission.CACHE_CLEAR,
    ],
    UserRole.PHYSICIAN: [
        # Triage
        Permission.TRIAGE_CREATE,
        Permission.TRIAGE_READ,
        Permission.TRIAGE_UPDATE,
        # Analysis (including HITL)
        Permission.ANALYSIS_CREATE,
        Permission.ANALYSIS_READ,
        Permission.ANALYSIS_APPROVE,
        Permission.ANALYSIS_REJECT,
        # Reports
        Permission.REPORT_READ,
        Permission.REPORT_EXPORT,
        # Limited metrics
        Permission.METRICS_VIEW,
    ],
    UserRole.PHARMACIST: [
        # Triage
        Permission.TRIAGE_CREATE,
        Permission.TRIAGE_READ,
        # Analysis and HITL review
        Permission.ANALYSIS_CREATE,
        Permission.ANALYSIS_READ,
        Permission.ANALYSIS_APPROVE,
        # Reports
        Permission.REPORT_READ,
    ],
    UserRole.READONLY: [
        # Read-only
        Permission.TRIAGE_READ,
        Permission.ANALYSIS_READ,
        Permission.REPORT_READ,
    ],
}


def check_permission(role: UserRole, permission: Permission) -> bool:
    """
    Check if a role has a specific permission

    Args:
        role: User role
        permission: Permission to check

    Returns:
        True if role has permission, False otherwise
    """
    return permission in ROLE_PERMISSIONS.get(role, [])


def check_role_hierarchy(user_role: UserRole, required_role: UserRole) -> bool:
    """
    Check if user role satisfies required role (considering hierarchy)

    Args:
        user_role: User's actual role
        required_role: Required minimum role

    Returns:
        True if user has sufficient permissions
    """
    return required_role in ROLE_HIERARCHY.get(user_role, [])


def get_user_from_db(user_id: str, db: Session):
    """
    Fetch user from database by ID

    SECURITY: Always fetch fresh user data from DB to prevent stale permissions
    """
    from ..db.user_models import User

    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None


class RoleChecker:
    """
    Dependency to check user role

    PATTERN: FastAPI dependency for authorization
    SKILL: @api-design-principles

    SECURITY FIX: Now properly verifies roles from database
    """

    def __init__(self, allowed_roles: List[UserRole]):
        """
        Initialize role checker

        Args:
            allowed_roles: List of roles that are allowed access
        """
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> str:
        """
        Check if current user has required role

        Args:
            current_user: User ID from JWT token
            db: Database session

        Returns:
            User ID if authorized

        Raises:
            HTTPException: If user lacks required role
        """
        # SECURITY FIX: Fetch user from database to verify role
        user = get_user_from_db(current_user, db)

        if not user:
            logger.warning(f"RBAC: User not found in database: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is active
        if not user.is_active:
            logger.warning(f"RBAC: Inactive user attempted access: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        # Check if user account is locked
        if user.is_locked():
            logger.warning(f"RBAC: Locked user attempted access: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is temporarily locked",
            )

        # SECURITY: Verify user has required role (considering hierarchy)
        user_has_permission = False
        for allowed_role in self.allowed_roles:
            if check_role_hierarchy(user.role, allowed_role):
                user_has_permission = True
                break

        if not user_has_permission:
            # FASE 1.2: Audit log for access denied
            audit_logger.access_denied(
                user_id=current_user,
                username=user.email,
                user_role=user.role.value,
                required_role=",".join([r.value for r in self.allowed_roles]),
                reason="role_insufficient",
            )

            logger.warning(
                f"RBAC: Access denied for user {current_user} "
                f"(role={user.role}, required={self.allowed_roles})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in self.allowed_roles]}",
            )

        logger.debug(f"RBAC: Access granted for user {current_user} (role={user.role})")
        return current_user


class PermissionChecker:
    """
    Dependency to check user permissions

    PATTERN: Fine-grained authorization
    SKILL: @api-design-principles

    SECURITY FIX: Now properly verifies permissions from database
    """

    def __init__(self, required_permissions: List[Permission]):
        """
        Initialize permission checker

        Args:
            required_permissions: List of required permissions
        """
        self.required_permissions = required_permissions

    async def __call__(
        self,
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> str:
        """
        Check if current user has required permissions

        Args:
            current_user: User ID from JWT token
            db: Database session

        Returns:
            User ID if authorized

        Raises:
            HTTPException: If user lacks required permissions
        """
        # SECURITY FIX: Fetch user from database to verify permissions
        user = get_user_from_db(current_user, db)

        if not user:
            logger.warning(f"PermissionChecker: User not found: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is active
        if not user.is_active:
            logger.warning(f"PermissionChecker: Inactive user: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        # Check if user account is locked
        if user.is_locked():
            logger.warning(f"PermissionChecker: Locked user: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is temporarily locked",
            )

        # SECURITY: Verify user has all required permissions
        missing_permissions = []
        for permission in self.required_permissions:
            if not check_permission(user.role, permission):
                missing_permissions.append(permission)

        if missing_permissions:
            logger.warning(
                f"PermissionChecker: Access denied for user {current_user} "
                f"(role={user.role}, missing={[p.value for p in missing_permissions]})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {[p.value for p in missing_permissions]}",
            )

        logger.debug(
            f"PermissionChecker: Access granted for user {current_user} "
            f"(role={user.role}, permissions={[p.value for p in self.required_permissions]})"
        )
        return current_user


# ============================================================================
# ROLE-BASED DEPENDENCIES (ready to use)
# ============================================================================

# Admin only
require_admin = RoleChecker([UserRole.ADMIN])

# Physician or above (physician + admin)
require_physician = RoleChecker([UserRole.ADMIN, UserRole.PHYSICIAN])

# Pharmacist or above (pharmacist + physician + admin)
require_pharmacist = RoleChecker(
    [UserRole.ADMIN, UserRole.PHYSICIAN, UserRole.PHARMACIST]
)

# Any authenticated user
require_authenticated = RoleChecker(
    [UserRole.ADMIN, UserRole.PHYSICIAN, UserRole.PHARMACIST, UserRole.READONLY]
)


# ============================================================================
# PERMISSION-BASED DEPENDENCIES
# ============================================================================

# Analysis permissions
can_create_analysis = PermissionChecker([Permission.ANALYSIS_CREATE])
can_approve_analysis = PermissionChecker([Permission.ANALYSIS_APPROVE])

# User management (admin only)
can_manage_users = PermissionChecker(
    [Permission.USER_CREATE, Permission.USER_UPDATE, Permission.USER_DELETE]
)

# System config (admin only)
can_configure_system = PermissionChecker([Permission.CONFIG_UPDATE])
