"""
Authentication Router - JWT with RBAC

PATTERN: Secure authentication with role-based access control
SKILLS: @api-design-principles, @secrets-management, @backend-dev-guidelines
FASE 1.2: Audit logging integration
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth.jwt import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    revoke_token,
    verify_refresh_token,
)
from ..auth.models import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    Token,
    User,
    UserCreate,
)
from ..auth.rbac import UserRole, require_admin
from ..db.database import get_db_context
from ..db.user_models import User as DBUser
from ..db.user_models import UserSession as DBUserSession
from ..middleware.rate_limit import limiter
from ..utils.audit_logger import AuditEventType, audit_logger

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v2/auth",
    tags=["authentication"],
)


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # Strict rate limit for registration
async def register_user(
    request: Request,
    user_data: UserCreate,
    current_user: str = Depends(require_admin),  # Only admins can create users
):
    """
    Register new user (Admin only)

    RBAC: Requires ADMIN role

    **Features:**
    - Email uniqueness validation
    - Password hashing with bcrypt
    - Role assignment
    - Audit logging

    **Rate limit:** 5 requests per hour per IP
    """
    with get_db_context() as db:
        # Check if email already exists
        existing_user = db.query(DBUser).filter(DBUser.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create new user
        new_user = DBUser(
            email=user_data.email,
            password_hash=DBUser.hash_password(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"New user registered: {new_user.email} (role: {new_user.role})")

        return User(
            id=str(new_user.id),
            email=new_user.email,
            full_name=new_user.full_name,
            is_active=new_user.is_active,
            is_superuser=new_user.role == UserRole.ADMIN,
            role=new_user.role,
            created_at=new_user.created_at,
        )


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # Prevent brute force
async def login(request: Request, credentials: LoginRequest):
    """
    User login with JWT tokens

    **Features:**
    - Email/password authentication
    - Account lockout after 5 failed attempts (30 min)
    - JWT access token (30 min expiry)
    - JWT refresh token (7 days expiry)
    - Audit logging

    **Rate limit:** 10 requests per minute per IP

    **Returns:**
    - access_token: Short-lived token for API requests
    - refresh_token: Long-lived token for renewing access
    """
    with get_db_context() as db:
        # Find user by email
        user = db.query(DBUser).filter(DBUser.email == credentials.email).first()

        if not user:
            # FASE 1.2: Log failed login (unknown user)
            audit_logger.auth_login_failed(
                username=credentials.email,
                client_ip=request.client.host if request.client else "unknown",
                reason="user_not_found",
                user_agent=request.headers.get("user-agent"),
                request_id=getattr(request.state, "request_id", None),
            )

            # Don't reveal if email exists
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Check if account is locked
        if user.is_locked():
            # FASE 1.2: Log locked account access attempt
            audit_logger.auth_login_failed(
                username=credentials.email,
                client_ip=request.client.host if request.client else "unknown",
                reason="account_locked",
                user_agent=request.headers.get("user-agent"),
                request_id=getattr(request.state, "request_id", None),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account locked due to multiple failed login attempts. Try again later.",
            )

        # Verify password
        if not user.verify_password(credentials.password):
            user.record_failed_login()
            db.commit()

            # FASE 1.2: Log wrong password attempt
            audit_logger.auth_login_failed(
                username=credentials.email,
                client_ip=request.client.host if request.client else "unknown",
                reason="invalid_password",
                user_agent=request.headers.get("user-agent"),
                request_id=getattr(request.state, "request_id", None),
                failed_attempts=user.failed_login_attempts,
            )

            logger.warning(f"Failed login attempt for user: {user.email}")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Check if user is active
        if not user.is_active:
            # FASE 1.2: Log disabled account access attempt
            audit_logger.auth_login_failed(
                username=credentials.email,
                client_ip=request.client.host if request.client else "unknown",
                reason="account_disabled",
                user_agent=request.headers.get("user-agent"),
                request_id=getattr(request.state, "request_id", None),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        # Successful login
        user.record_successful_login()
        db.commit()

        # SECURITY FIX: Create tokens with device tracking
        device_id = request.headers.get("X-Device-ID")
        access_token, access_jti = create_access_token(
            data={"sub": str(user.id), "role": user.role.value}, device_id=device_id
        )
        refresh_token_str, refresh_jti = create_refresh_token(
            data={"sub": str(user.id)}, device_id=device_id
        )

        # Store refresh token session in database (user_sessions)
        refresh_session = DBUserSession(
            user_id=user.id,
            jti=refresh_jti,
            expires_at=datetime.utcnow() + timedelta(days=7),
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            device_info=device_id,
        )

        db.add(refresh_session)
        db.commit()

        # FASE 1.2: Log successful login
        audit_logger.auth_login_success(
            user_id=str(user.id),
            username=user.email,
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            request_id=getattr(request.state, "request_id", None),
            role=user.role.value,
        )

        # FASE 1.2: Log token creation
        audit_logger.token_created(
            user_id=str(user.id),
            token_type="access",
            jti=access_jti,
            client_ip=request.client.host if request.client else "unknown",
            request_id=getattr(request.state, "request_id", None),
        )

        logger.info(f"User logged in: {user.email} (role: {user.role})")

        return Token(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=1800,  # 30 minutes
        )


@router.post("/refresh", response_model=Token)
@limiter.limit("20/hour")
async def refresh_token(request: Request, refresh_request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    **Features:**
    - Token rotation (new refresh token issued)
    - Revocation support
    - Expiry validation

    **Rate limit:** 20 requests per hour per IP

    SECURITY FIX: Agora usa verify_refresh_token (função separada)
    """
    try:
        # SECURITY FIX: Usar função específica para refresh tokens
        payload = verify_refresh_token(refresh_request.refresh_token)

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        with get_db_context() as db:
            # Verify refresh token session in database (by JTI)
            refresh_jti = payload.get("jti")
            if not refresh_jti:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token (missing jti)",
                )

            stored_session = (
                db.query(DBUserSession)
                .filter(DBUserSession.jti == str(refresh_jti))
                .filter(DBUserSession.user_id == user_id)
                .first()
            )

            if (
                not stored_session
                or (not stored_session.is_active)
                or stored_session.is_expired()
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token",
                )

            # Get user
            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                )

            # Revoke old refresh session (token rotation)
            stored_session.revoke(reason="token_rotation")

            # SECURITY FIX: Create new tokens with device tracking
            device_id = request.headers.get("X-Device-ID")
            access_token, access_jti = create_access_token(
                data={"sub": str(user.id), "role": user.role.value}, device_id=device_id
            )
            new_refresh_token, refresh_jti = create_refresh_token(
                data={"sub": str(user.id)}, device_id=device_id
            )

            # Store new refresh session
            new_refresh_session = DBUserSession(
                user_id=user.id,
                jti=refresh_jti,
                expires_at=datetime.utcnow() + timedelta(days=7),
                user_agent=request.headers.get("user-agent"),
                ip_address=request.client.host if request.client else None,
                device_info=device_id,
            )

            db.add(new_refresh_session)
            db.commit()

            logger.info(f"Token refreshed for user: {user.email}")

            return Token(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=1800,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
        )


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    refresh_request: RefreshTokenRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Logout user and revoke refresh token

    **Features:**
    - Revokes refresh token
    - Prevents token reuse

    **Rate limit:** 30 requests per minute
    """
    with get_db_context() as db:
        # Decode refresh token to find its jti and revoke the session in DB.
        payload = verify_refresh_token(refresh_request.refresh_token)
        refresh_jti = payload.get("jti")
        if refresh_jti:
            stored_session = (
                db.query(DBUserSession)
                .filter(DBUserSession.jti == str(refresh_jti))
                .filter(DBUserSession.user_id == current_user)
                .first()
            )
            if stored_session:
                stored_session.revoke(reason="logout")
                db.commit()

        # Best-effort: revoke access token via Redis blacklist (if enabled and token provided)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            from ..auth.jwt import verify_token  # local import to avoid cycles

            access_token = auth_header.split(" ", 1)[1].strip()
            try:
                access_payload = verify_token(
                    access_token, expected_type="access", check_revocation=False
                )
                access_jti = access_payload.get("jti")
                access_exp = access_payload.get("exp")
                if access_jti and access_exp:
                    await revoke_token(
                        jti=str(access_jti),
                        exp=datetime.utcfromtimestamp(int(access_exp)),
                    )
            except Exception:
                # Ignore failures (logout should still succeed)
                pass

        # FASE 1.2: Log logout
        audit_logger.auth_logout(
            user_id=current_user,
            username="",  # Not available in this context
            client_ip=request.client.host if request.client else "unknown",
            request_id=getattr(request.state, "request_id", None),
        )

        logger.info(f"User logged out: {current_user}")

        return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
async def get_current_user_profile(current_user: str = Depends(get_current_user)):
    """
    Get current authenticated user profile

    **Authentication:** Required
    """
    with get_db_context() as db:
        user = db.query(DBUser).filter(DBUser.id == current_user).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return User(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.role == UserRole.ADMIN,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


@router.post("/change-password")
@limiter.limit("5/hour")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: str = Depends(get_current_user),
) -> dict[str, str]:
    """Rotate the authenticated user's password and revoke refresh sessions."""
    with get_db_context() as db:
        user = db.query(DBUser).filter(DBUser.id == current_user).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.verify_password(password_data.current_password):
            raise HTTPException(status_code=400, detail="Current password is invalid")
        if user.verify_password(password_data.new_password):
            raise HTTPException(
                status_code=400, detail="New password must differ from current password"
            )

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Invalid access token")

        from ..auth.jwt import verify_token

        token_payload = verify_token(
            auth_header.split(" ", 1)[1].strip(),
            expected_type="access",
            check_revocation=False,
        )
        token_jti = token_payload.get("jti")
        token_exp = token_payload.get("exp")
        if not token_jti or not token_exp:
            raise HTTPException(status_code=401, detail="Invalid access token")

        try:
            revoked = await revoke_token(
                str(token_jti),
                datetime.fromtimestamp(int(token_exp), tz=timezone.utc),
            )
        except Exception as exc:
            logger.error(
                "Could not revoke access token during password change: %s", exc
            )
            raise HTTPException(
                status_code=503, detail="Token revocation unavailable"
            ) from exc
        if not revoked:
            raise HTTPException(status_code=503, detail="Token revocation unavailable")

        user.password_hash = DBUser.hash_password(password_data.new_password)
        user.last_password_change = datetime.now(timezone.utc)
        sessions = (
            db.query(DBUserSession)
            .filter(DBUserSession.user_id == current_user)
            .filter(DBUserSession.is_active.is_(True))
            .all()
        )
        for session in sessions:
            session.revoke(reason="password_change")
        db.commit()

        user_email = user.email
        user_role = user.role.value

    await audit_logger.log(
        AuditEventType.PASSWORD_CHANGE,
        "password_changed",
        user_id=current_user,
        user_email=user_email,
        user_role=user_role,
    )
    return {"message": "Password changed; sign in again"}


# ============================================================================
# ADMIN USER MANAGEMENT
# ============================================================================


@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users(current_user: str = Depends(require_admin)):
    """
    List all users (Admin only)

    RBAC: Requires ADMIN role
    """
    with get_db_context() as db:
        users = db.query(DBUser).all()

        return [
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }
            for user in users
        ]
