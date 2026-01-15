"""
Audit Logger para MedSafe.

Este módulo fornece funcionalidades de logging de auditoria para rastreamento
de segurança, compliance LGPD e monitoramento de atividades.
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import Request


logger = logging.getLogger("medsafe.audit")


class AuditEventType(str, Enum):
    """Tipos de eventos de auditoria."""
    
    # Autenticação
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKE = "token_revoke"
    TOKEN_CREATED = "token_created"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"

    # Backwards-compatible aliases expected by some tests/legacy code
    AUTH_LOGIN_SUCCESS = LOGIN_SUCCESS
    AUTH_LOGIN_FAILED = LOGIN_FAILURE
    
    # Autorização
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHECK = "permission_check"
    
    # Operações de dados
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # Análises médicas
    ANALYSIS_START = "analysis_start"
    ANALYSIS_COMPLETE = "analysis_complete"
    ANALYSIS_ERROR = "analysis_error"
    
    # HITL
    HITL_REQUIRED = "hitl_required"
    HITL_APPROVE = "hitl_approve"
    HITL_REJECT = "hitl_reject"
    
    # Sistema
    CONFIG_CHANGE = "config_change"
    SECURITY_ALERT = "security_alert"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # LGPD
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    DATA_ANONYMIZED = "data_anonymized"
    DATA_DELETION_REQUEST = "data_deletion_request"


class AuditCategory(str, Enum):
    """Categorias de eventos para agrupamento."""
    
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    MEDICAL_ANALYSIS = "medical_analysis"
    HITL = "hitl"
    SYSTEM = "system"
    SECURITY = "security"
    LGPD = "lgpd"


class AuditSeverity(str, Enum):
    """Níveis de severidade de eventos."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditLogger:
    """
    Logger de auditoria centralizado.
    
    Fornece métodos para registrar eventos de segurança e compliance,
    com suporte a persistência em banco de dados e logging estruturado.
    """
    
    def __init__(self):
        self._db_enabled = True
        self._request_context: Optional[Request] = None
        
    def set_db_enabled(self, enabled: bool) -> None:
        """Habilita/desabilita persistência no banco."""
        self._db_enabled = enabled
    
    @contextmanager
    def request_context(self, request: Request):
        """Context manager para associar logs a uma requisição."""
        self._request_context = request
        try:
            yield
        finally:
            self._request_context = None
    
    def _get_request_info(self) -> Dict[str, Any]:
        """Extrai informações da requisição atual."""
        info = {
            "request_id": None,
            "ip_address": None,
            "user_agent": None,
            "endpoint": None,
            "http_method": None,
        }
        
        if self._request_context:
            info["request_id"] = getattr(self._request_context.state, "request_id", None)
            info["ip_address"] = self._get_client_ip(self._request_context)
            info["user_agent"] = self._request_context.headers.get("user-agent", "")[:500]
            info["endpoint"] = str(self._request_context.url.path)
            info["http_method"] = self._request_context.method
            
        return info
    
    def _get_client_ip(self, request: Request) -> str:
        """Extrai IP do cliente, considerando proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
            
        return request.client.host if request.client else "unknown"
    
    def _serialize_details(self, details: Any) -> Optional[str]:
        """Serializa detalhes para JSON."""
        if details is None:
            return None
        
        try:
            if isinstance(details, str):
                return details[:2000]
            return json.dumps(details, default=str)[:2000]
        except Exception:
            return str(details)[:2000]
    
    async def log(
        self,
        event_type: AuditEventType,
        action: str,
        *,
        category: Optional[AuditCategory] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Any] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        persist: bool = True,
    ) -> str:
        """
        Registra um evento de auditoria.
        
        Args:
            event_type: Tipo do evento (AuditEventType)
            action: Ação específica executada
            category: Categoria do evento para agrupamento
            severity: Nível de severidade
            user_id: ID do usuário que executou a ação
            user_email: Email do usuário
            user_role: Role do usuário
            resource_type: Tipo do recurso afetado
            resource_id: ID do recurso afetado
            details: Detalhes adicionais (dict ou string)
            success: Se a operação foi bem-sucedida
            error_message: Mensagem de erro (se houver)
            persist: Se deve persistir no banco de dados
            
        Returns:
            ID único do evento de auditoria
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Inferir categoria se não fornecida
        if category is None:
            category = self._infer_category(event_type)
        
        # Obter informações da requisição
        request_info = self._get_request_info()
        
        # Estrutura do log
        log_entry = {
            "event_id": event_id,
            "timestamp": timestamp,
            "event_type": event_type.value,
            "category": category.value,
            "severity": severity.value,
            "action": action,
            "user_id": user_id,
            "user_email": user_email,
            "user_role": user_role,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "success": success,
            "error_message": error_message,
            **request_info,
            "details": self._serialize_details(details),
        }
        
        # Log estruturado
        log_level = getattr(logging, severity.value)
        logger.log(
            log_level,
            f"[AUDIT] {event_type.value}:{action}",
            extra={"audit_data": log_entry}
        )
        
        # Persistir no banco se habilitado
        if persist and self._db_enabled:
            await self._persist_to_db(log_entry)
        
        return event_id

    def _format_event(self, event: "AuditEvent") -> Dict[str, Any]:
        """Format an AuditEvent into a dict (compat helper for tests)."""
        return {
            "event_type": event.event_type.value if isinstance(event.event_type, AuditEventType) else str(event.event_type),
            "severity": event.severity.value if isinstance(event.severity, AuditSeverity) else str(event.severity),
            "timestamp": event.timestamp,
            "user_id": event.user_id,
            "details": event.details,
        }
    
    def _infer_category(self, event_type: AuditEventType) -> AuditCategory:
        """Infere a categoria baseado no tipo de evento."""
        category_map = {
            AuditEventType.LOGIN_SUCCESS: AuditCategory.AUTHENTICATION,
            AuditEventType.LOGIN_FAILURE: AuditCategory.AUTHENTICATION,
            AuditEventType.LOGOUT: AuditCategory.AUTHENTICATION,
            AuditEventType.TOKEN_REFRESH: AuditCategory.AUTHENTICATION,
            AuditEventType.TOKEN_REVOKE: AuditCategory.AUTHENTICATION,
            AuditEventType.TOKEN_CREATED: AuditCategory.AUTHENTICATION,
            AuditEventType.PASSWORD_CHANGE: AuditCategory.AUTHENTICATION,
            AuditEventType.PASSWORD_RESET: AuditCategory.AUTHENTICATION,
            
            AuditEventType.ACCESS_GRANTED: AuditCategory.AUTHORIZATION,
            AuditEventType.ACCESS_DENIED: AuditCategory.AUTHORIZATION,
            AuditEventType.PERMISSION_CHECK: AuditCategory.AUTHORIZATION,
            
            AuditEventType.DATA_CREATE: AuditCategory.DATA_ACCESS,
            AuditEventType.DATA_READ: AuditCategory.DATA_ACCESS,
            AuditEventType.DATA_UPDATE: AuditCategory.DATA_ACCESS,
            AuditEventType.DATA_DELETE: AuditCategory.DATA_ACCESS,
            AuditEventType.DATA_EXPORT: AuditCategory.DATA_ACCESS,
            
            AuditEventType.ANALYSIS_START: AuditCategory.MEDICAL_ANALYSIS,
            AuditEventType.ANALYSIS_COMPLETE: AuditCategory.MEDICAL_ANALYSIS,
            AuditEventType.ANALYSIS_ERROR: AuditCategory.MEDICAL_ANALYSIS,
            
            AuditEventType.HITL_REQUIRED: AuditCategory.HITL,
            AuditEventType.HITL_APPROVE: AuditCategory.HITL,
            AuditEventType.HITL_REJECT: AuditCategory.HITL,
            
            AuditEventType.CONFIG_CHANGE: AuditCategory.SYSTEM,
            AuditEventType.SECURITY_ALERT: AuditCategory.SECURITY,
            AuditEventType.RATE_LIMIT_EXCEEDED: AuditCategory.SECURITY,
            
            AuditEventType.CONSENT_GRANTED: AuditCategory.LGPD,
            AuditEventType.CONSENT_REVOKED: AuditCategory.LGPD,
            AuditEventType.DATA_ANONYMIZED: AuditCategory.LGPD,
            AuditEventType.DATA_DELETION_REQUEST: AuditCategory.LGPD,
        }
        
        return category_map.get(event_type, AuditCategory.SYSTEM)
    
    async def _persist_to_db(self, log_entry: Dict[str, Any]) -> None:
        """Persiste o log de auditoria no banco de dados."""
        try:
            from ..db.database import get_db_context
            from ..db.user_models import AuditLog
            
            with get_db_context() as db:
                audit_log = AuditLog(
                    event_type=log_entry["event_type"],
                    event_category=log_entry["category"],
                    severity=log_entry["severity"],
                    user_id=log_entry.get("user_id"),
                    user_email=log_entry.get("user_email"),
                    user_role=log_entry.get("user_role"),
                    ip_address=log_entry.get("ip_address"),
                    user_agent=log_entry.get("user_agent"),
                    request_id=log_entry.get("request_id"),
                    endpoint=log_entry.get("endpoint"),
                    http_method=log_entry.get("http_method"),
                    resource_type=log_entry.get("resource_type"),
                    resource_id=log_entry.get("resource_id"),
                    action=log_entry["action"],
                    details=log_entry.get("details"),
                    success=log_entry.get("success", True),
                    error_message=log_entry.get("error_message"),
                )
                db.add(audit_log)
                db.commit()
                
        except Exception as e:
            # Não falhar silenciosamente, mas também não quebrar a aplicação
            logger.error(f"Falha ao persistir audit log: {e}")
    
    # Métodos de conveniência para eventos comuns
    
    async def log_login_success(
        self,
        user_id: str,
        user_email: str,
        user_role: str,
        details: Optional[Dict] = None,
    ) -> str:
        """Registra login bem-sucedido."""
        return await self.log(
            AuditEventType.LOGIN_SUCCESS,
            "user_authenticated",
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            details=details or {"method": "password"},
        )
    
    async def log_login_failure(
        self,
        email: str,
        reason: str,
        details: Optional[Dict] = None,
    ) -> str:
        """Registra tentativa de login falhada."""
        return await self.log(
            AuditEventType.LOGIN_FAILURE,
            "login_attempt_failed",
            severity=AuditSeverity.WARNING,
            user_email=email,
            success=False,
            error_message=reason,
            details=details,
        )
    
    async def log_access_denied(
        self,
        user_id: Optional[str],
        user_email: Optional[str],
        resource: str,
        reason: str,
    ) -> str:
        """Registra acesso negado."""
        return await self.log(
            AuditEventType.ACCESS_DENIED,
            "access_denied",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            user_email=user_email,
            resource_type=resource,
            success=False,
            error_message=reason,
        )
    
    async def log_analysis_start(
        self,
        user_id: str,
        session_id: str,
        patient_data: Optional[Dict] = None,
    ) -> str:
        """Registra início de análise médica."""
        return await self.log(
            AuditEventType.ANALYSIS_START,
            "analysis_initiated",
            user_id=user_id,
            resource_type="analysis",
            resource_id=session_id,
            details={"patient_data_provided": bool(patient_data)},
        )
    
    async def log_analysis_complete(
        self,
        user_id: str,
        session_id: str,
        risk_level: str,
        interactions_found: int,
    ) -> str:
        """Registra conclusão de análise médica."""
        return await self.log(
            AuditEventType.ANALYSIS_COMPLETE,
            "analysis_completed",
            user_id=user_id,
            resource_type="analysis",
            resource_id=session_id,
            details={
                "risk_level": risk_level,
                "interactions_found": interactions_found,
            },
        )
    
    async def log_hitl_decision(
        self,
        user_id: str,
        user_email: str,
        session_id: str,
        decision: str,  # "approved" ou "rejected"
        reason: Optional[str] = None,
    ) -> str:
        """Registra decisão HITL."""
        event_type = (
            AuditEventType.HITL_APPROVE 
            if decision == "approved" 
            else AuditEventType.HITL_REJECT
        )
        
        return await self.log(
            event_type,
            f"hitl_{decision}",
            severity=AuditSeverity.INFO if decision == "approved" else AuditSeverity.WARNING,
            user_id=user_id,
            user_email=user_email,
            resource_type="analysis",
            resource_id=session_id,
            details={"reason": reason} if reason else None,
        )
    
    async def log_security_alert(
        self,
        alert_type: str,
        description: str,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None,
    ) -> str:
        """Registra alerta de segurança."""
        return await self.log(
            AuditEventType.SECURITY_ALERT,
            alert_type,
            severity=AuditSeverity.CRITICAL,
            user_id=user_id,
            success=False,
            error_message=description,
            details=details,
        )
    
    async def log_rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Registra rate limit excedido."""
        return await self.log(
            AuditEventType.RATE_LIMIT_EXCEEDED,
            "rate_limit_exceeded",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            details={
                "ip_address": ip_address,
                "endpoint": endpoint,
            },
        )
    
    async def log_data_deletion_request(
        self,
        user_id: str,
        user_email: str,
        reason: str,
    ) -> str:
        """Registra solicitação de exclusão de dados (LGPD)."""
        return await self.log(
            AuditEventType.DATA_DELETION_REQUEST,
            "data_deletion_requested",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            user_email=user_email,
            details={"reason": reason},
        )
    
    # Versões síncronas para uso em contextos não-async
    
    def log_sync(
        self,
        event_type: AuditEventType,
        action: str,
        **kwargs
    ) -> str:
        """
        Versão síncrona do log (para uso em contextos não-async).
        
        Apenas faz log estruturado, sem persistência no banco.
        """
        import asyncio
        
        # Tentar executar em event loop existente
        try:
            loop = asyncio.get_running_loop()
            # Se há um loop rodando, agendar como task
            future = asyncio.ensure_future(self.log(event_type, action, **kwargs))
            return str(uuid4())  # Retornar ID temporário
        except RuntimeError:
            # Não há event loop, fazer log apenas
            event_id = str(uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            log_entry = {
                "event_id": event_id,
                "timestamp": timestamp,
                "event_type": event_type.value,
                "action": action,
                **kwargs,
            }
            
            severity = kwargs.get("severity", AuditSeverity.INFO)
            log_level = getattr(logging, severity.value if isinstance(severity, AuditSeverity) else severity)
            
            logger.log(
                log_level,
                f"[AUDIT-SYNC] {event_type.value}:{action}",
                extra={"audit_data": log_entry}
            )
            
            return event_id

    # ------------------------------------------------------------------
    # Compatibility wrappers (used by routers/rbac without `await`)
    # ------------------------------------------------------------------
    def auth_login_failed(
        self,
        *,
        username: str,
        client_ip: str,
        reason: str,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        failed_attempts: Optional[int] = None,
    ) -> str:
        return self.log_sync(
            AuditEventType.LOGIN_FAILURE,
            "login_attempt_failed",
            severity=AuditSeverity.WARNING,
            user_email=username,
            success=False,
            error_message=reason,
            details={
                "client_ip": client_ip,
                "user_agent": (user_agent or "")[:500] if user_agent else None,
                "request_id": request_id,
                "failed_attempts": failed_attempts,
            },
        )

    def auth_login_success(
        self,
        *,
        user_id: str,
        username: str,
        client_ip: str,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> str:
        return self.log_sync(
            AuditEventType.LOGIN_SUCCESS,
            "user_authenticated",
            severity=AuditSeverity.INFO,
            user_id=user_id,
            user_email=username,
            user_role=role,
            success=True,
            details={
                "client_ip": client_ip,
                "user_agent": (user_agent or "")[:500] if user_agent else None,
                "request_id": request_id,
            },
        )

    def token_created(
        self,
        *,
        user_id: str,
        token_type: str,
        jti: str,
        client_ip: str,
        request_id: Optional[str] = None,
    ) -> str:
        return self.log_sync(
            AuditEventType.TOKEN_CREATED,
            "token_created",
            severity=AuditSeverity.INFO,
            user_id=user_id,
            resource_type="token",
            resource_id=jti,
            success=True,
            details={
                "token_type": token_type,
                "client_ip": client_ip,
                "request_id": request_id,
            },
        )

    def auth_logout(
        self,
        *,
        user_id: str,
        username: str,
        client_ip: str,
        request_id: Optional[str] = None,
    ) -> str:
        return self.log_sync(
            AuditEventType.LOGOUT,
            "logout",
            severity=AuditSeverity.INFO,
            user_id=user_id,
            user_email=username or None,
            success=True,
            details={
                "client_ip": client_ip,
                "request_id": request_id,
            },
        )

    def access_denied(
        self,
        *,
        user_id: str,
        username: str,
        user_role: str,
        required_role: str,
        reason: str,
    ) -> str:
        return self.log_sync(
            AuditEventType.ACCESS_DENIED,
            "access_denied",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            user_email=username,
            user_role=user_role,
            resource_type="rbac",
            success=False,
            error_message=reason,
            details={
                "required_role": required_role,
            },
        )


# Instância global do audit logger
audit_logger = AuditLogger()


# Exportações
__all__ = [
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditCategory", 
    "AuditSeverity",
    "log_auth_success",
    "log_auth_failure",
    "log_access_denied",
    "log_token_revoked",
    "log_medical_analysis",
    "audit_logger",
]


@dataclass
class AuditEvent:
    """Lightweight audit event model (mainly for tests/compat)."""

    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Module-level helper functions (compat with older code/tests)
# ---------------------------------------------------------------------------
def log_auth_success(*, user_id: str, username: str, client_ip: str) -> str:
    return audit_logger.auth_login_success(user_id=user_id, username=username, client_ip=client_ip)


def log_auth_failure(*, username: str, client_ip: str, reason: str) -> str:
    return audit_logger.auth_login_failed(username=username, client_ip=client_ip, reason=reason)


def log_access_denied(*, user_id: str, endpoint: str) -> str:
    return audit_logger.log_sync(
        AuditEventType.ACCESS_DENIED,
        "access_denied",
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        resource_type="endpoint",
        details={"endpoint": endpoint},
        success=False,
    )


def log_token_revoked(*, user_id: str, jti: str, reason: str) -> str:
    return audit_logger.log_sync(
        AuditEventType.TOKEN_REVOKE,
        "token_revoked",
        severity=AuditSeverity.INFO,
        user_id=user_id,
        resource_type="token",
        resource_id=jti,
        details={"reason": reason},
        success=True,
    )


def log_medical_analysis(*, user_id: str, analysis_type: str) -> str:
    return audit_logger.log_sync(
        AuditEventType.ANALYSIS_START,
        "analysis_started",
        severity=AuditSeverity.INFO,
        user_id=user_id,
        resource_type="analysis",
        details={"analysis_type": analysis_type},
        success=True,
    )
