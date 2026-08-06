"""
User Models para MedSafe.

Este módulo define os modelos de usuário necessários para autenticação JWT e RBAC.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from ..auth.rbac import Permission, UserRole
from .database import Base, is_sqlite

# Tipo UUID compatível com SQLite e PostgreSQL
if is_sqlite:
    UUIDType = String(36)
else:
    UUIDType = PGUUID(as_uuid=True)


class User(Base):
    """
    Modelo de usuário para autenticação e autorização.

    Atributos:
        id: Identificador único do usuário (UUID)
        email: E-mail único do usuário (usado para login)
        password_hash: Hash BCrypt da senha
        full_name: Nome completo do usuário
        role: Papel do usuário (ADMIN, PHYSICIAN, PHARMACIST, READONLY)
        is_active: Se o usuário está ativo
        is_verified: Se o e-mail foi verificado
        locked_until: Data/hora até quando o usuário está bloqueado
        failed_login_attempts: Número de tentativas de login falhadas
        last_login: Data/hora do último login
        created_at: Data/hora de criação
        updated_at: Data/hora da última atualização
        crm: Número do CRM (para médicos)
        crf: Número do CRF (para farmacêuticos)
        specialty: Especialidade médica (se aplicável)
    """

    __tablename__ = "users"

    # Campos de identificação
    id = Column(
        UUIDType,
        primary_key=True,
        default=lambda: str(uuid4()) if is_sqlite else uuid4(),
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)

    # Campos de autorização
    role = Column(
        Enum(
            UserRole,
            name="user_role_enum",
            create_constraint=True,
            # CRITICAL: o enum do Postgres usa os VALORES minúsculos
            # ("admin", "physician", ...). Sem values_callable, SQLAlchemy
            # persiste os NOMES ("ADMIN", ...) e quebra INSERT (register)
            # e SELECT (LookupError ao ler usuários existentes).
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=UserRole.READONLY,
        nullable=False,
        index=True,
    )

    # Status da conta
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Segurança
    locked_until = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_password_change = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    # Campos profissionais (para compliance médica)
    crm = Column(
        String(20), nullable=True, unique=True
    )  # Conselho Regional de Medicina
    crf = Column(
        String(20), nullable=True, unique=True
    )  # Conselho Regional de Farmácia
    specialty = Column(String(100), nullable=True)

    # Soft delete para LGPD
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Preferências do usuário
    notification_preferences = Column(
        String(500), default='{"email": true, "sms": false}'
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"

    # ------------------------------------------------------------------
    # Password helpers (used by auth router)
    # ------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with bcrypt (delegates to app auth utilities)."""
        from ..auth.password import hash_password as _hash

        return _hash(password)

    def verify_password(self, plain_password: str) -> bool:
        """Verify password against stored hash."""
        from ..auth.password import verify_password as _verify

        return _verify(plain_password, self.password_hash)

    def is_locked(self) -> bool:
        """Verifica se a conta está bloqueada por tentativas de login."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until.replace(tzinfo=None)
        return False

    def lock_account(self, duration_minutes: int = 30) -> None:
        """Bloqueia a conta por um período."""
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)

    def unlock_account(self) -> None:
        """Desbloqueia a conta."""
        self.locked_until = None
        self.failed_login_attempts = 0

    def increment_failed_login(self) -> None:
        """
        Incrementa contador de falhas e bloqueia após limite.

        Lógica de bloqueio progressivo:
        - 3-5 falhas: Aviso
        - 5-10 falhas: Bloqueio de 5 minutos
        - 10+ falhas: Bloqueio de 30 minutos
        """
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= 10:
            self.lock_account(duration_minutes=30)
        elif self.failed_login_attempts >= 5:
            self.lock_account(duration_minutes=5)

    # Compatibility aliases (older router expectations)
    def record_failed_login(self) -> None:
        """Alias for increment_failed_login()."""
        self.increment_failed_login()

    def record_successful_login(self) -> None:
        """Alias for reset_failed_login()."""
        self.reset_failed_login()

    def reset_failed_login(self) -> None:
        """Reseta contador de falhas após login bem-sucedido."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.utcnow()

    def soft_delete(self) -> None:
        """Soft delete para conformidade LGPD."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.is_active = False
        # Anonimizar dados sensíveis
        self.email = f"deleted_{self.id}@medsafe.local"
        self.full_name = "Usuário Removido"
        self.password_hash = "DELETED"
        self.crm = None
        self.crf = None

    def get_permissions(self) -> set[Permission]:
        """
        Retorna as permissões do usuário baseadas no seu role.

        Returns:
            Set de Permission que o usuário possui
        """
        from ..auth.rbac import ROLE_PERMISSIONS

        return ROLE_PERMISSIONS.get(self.role, set())

    def has_permission(self, permission: Permission) -> bool:
        """
        Verifica se o usuário tem uma permissão específica.

        Args:
            permission: Permission a verificar

        Returns:
            True se o usuário tem a permissão
        """
        return permission in self.get_permissions()

    def can_access_patient_data(self) -> bool:
        """Verifica se pode acessar dados de pacientes."""
        return self.has_permission(Permission.TRIAGE_READ)

    def can_create_analysis(self) -> bool:
        """Verifica se pode criar análises."""
        return self.has_permission(Permission.TRIAGE_CREATE)

    def can_approve_hitl(self) -> bool:
        """Verifica se pode aprovar HITL."""
        return self.has_permission(Permission.HITL_APPROVE)

    def is_healthcare_professional(self) -> bool:
        """Verifica se é profissional de saúde registrado."""
        return bool(self.crm or self.crf)


class UserSession(Base):
    """
    Modelo para sessões ativas de usuário.

    Permite rastrear e revogar sessões específicas.
    """

    __tablename__ = "user_sessions"

    id = Column(
        UUIDType,
        primary_key=True,
        default=lambda: str(uuid4()) if is_sqlite else uuid4(),
    )
    user_id = Column(UUIDType, nullable=False, index=True)
    jti = Column(String(36), unique=True, nullable=False, index=True)  # JWT ID

    # Informações da sessão
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    device_info = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoke_reason = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), default=func.now())

    def __repr__(self) -> str:
        status = "active" if self.is_active else "revoked"
        return f"<UserSession {self.jti[:8]}... ({status})>"

    def revoke(self, reason: str = "Manual revocation") -> None:
        """Revoga esta sessão."""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoke_reason = reason

    def is_expired(self) -> bool:
        """Verifica se a sessão expirou."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at.replace(tzinfo=None)
        return True

    def update_activity(self) -> None:
        """Atualiza timestamp de última atividade."""
        self.last_activity = datetime.utcnow()


class AuditLog(Base):
    """
    Modelo para logs de auditoria de segurança.

    Registra todas as ações relevantes para compliance LGPD e segurança.
    """

    __tablename__ = "audit_logs"

    id = Column(
        UUIDType,
        primary_key=True,
        default=lambda: str(uuid4()) if is_sqlite else uuid4(),
    )

    # Identificação do evento
    event_type = Column(String(50), nullable=False, index=True)
    event_category = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), default="INFO", nullable=False)

    # Quem executou
    user_id = Column(UUIDType, nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)

    # Contexto da requisição
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(36), nullable=True, index=True)
    endpoint = Column(String(255), nullable=True)
    http_method = Column(String(10), nullable=True)

    # Detalhes do evento
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(String(2000), nullable=True)  # JSON string

    # Resultado
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(String(500), nullable=True)

    # Timestamp
    created_at = Column(
        DateTime(timezone=True), default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type}:{self.action} at {self.created_at}>"


# Exportar modelos
__all__ = ["User", "UserSession", "AuditLog"]
