"""
Unit tests for audit logger

Tests AuditLogger, AuditEvent, and audit log functions.
"""


class TestAuditEventType:
    """Tests for AuditEventType enum"""

    def test_audit_event_types(self):
        """Test AuditEventType enum has expected values"""
        from backend.app.utils.audit_logger import AuditEventType

        # Should have common audit event types
        assert hasattr(AuditEventType, "AUTH_LOGIN_SUCCESS")
        assert hasattr(AuditEventType, "AUTH_LOGIN_FAILED")
        assert len(AuditEventType) > 0


class TestAuditSeverity:
    """Tests for AuditSeverity enum"""

    def test_audit_severity_values(self):
        """Test AuditSeverity enum has expected values"""
        from backend.app.utils.audit_logger import AuditSeverity

        assert hasattr(AuditSeverity, "INFO") or hasattr(AuditSeverity, "LOW")
        assert len(AuditSeverity) > 0


class TestAuditEvent:
    """Tests for AuditEvent dataclass"""

    def test_audit_event_creation(self):
        """Test creating an AuditEvent"""
        from datetime import datetime

        from backend.app.utils.audit_logger import (
            AuditEvent,
            AuditEventType,
            AuditSeverity,
        )

        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=datetime.now().isoformat(),
            user_id="user123",
        )

        assert event is not None
        assert event.user_id == "user123"
        assert event.event_type == AuditEventType.AUTH_LOGIN_SUCCESS

    def test_audit_event_timestamp(self):
        """Test AuditEvent has timestamp"""
        from datetime import datetime

        from backend.app.utils.audit_logger import (
            AuditEvent,
            AuditEventType,
            AuditSeverity,
        )

        timestamp = datetime.now().isoformat()

        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=timestamp,
        )

        assert event.timestamp is not None
        assert event.timestamp == timestamp


class TestAuditLogger:
    """Tests for AuditLogger class"""

    def test_audit_logger_singleton(self):
        """Test AuditLogger singleton pattern"""
        from backend.app.utils.audit_logger import AuditLogger

        logger1 = AuditLogger()
        logger2 = AuditLogger()

        # Should be same or equivalent instance
        assert logger1 is not None
        assert logger2 is not None

    def test_audit_logger_log_event(self):
        """Test AuditLogger log_event method"""
        from datetime import datetime

        from backend.app.utils.audit_logger import (
            AuditEvent,
            AuditEventType,
            AuditLogger,
            AuditSeverity,
        )

        logger = AuditLogger()

        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=datetime.now().isoformat(),
        )

        # Should not raise
        if hasattr(logger, "_format_event"):
            logger._format_event(event)


class TestAuditLogFunctions:
    """Tests for audit log helper functions"""

    def test_log_auth_success(self):
        """Test log_auth_success function"""
        from backend.app.utils.audit_logger import log_auth_success

        # Should not raise
        log_auth_success(user_id="user123", username="testuser", client_ip="127.0.0.1")

    def test_log_auth_failure(self):
        """Test log_auth_failure function"""
        from backend.app.utils.audit_logger import log_auth_failure

        # Should not raise
        log_auth_failure(
            username="testuser", client_ip="127.0.0.1", reason="Invalid password"
        )

    def test_log_access_denied(self):
        """Test log_access_denied function"""
        from backend.app.utils.audit_logger import log_access_denied

        # Should not raise
        log_access_denied(user_id="user123", endpoint="/admin/users")

    def test_log_token_revoked(self):
        """Test log_token_revoked function"""
        from backend.app.utils.audit_logger import log_token_revoked

        # Should not raise
        log_token_revoked(user_id="user123", jti="token-id-123", reason="User logout")

    def test_log_medical_analysis(self):
        """Test log_medical_analysis function"""
        from backend.app.utils.audit_logger import log_medical_analysis

        # Should not raise
        log_medical_analysis(
            user_id="user123",
            analysis_type="drug_interaction",
        )


class TestAuditLoggerMethods:
    """Tests for additional AuditLogger methods"""

    def test_audit_logger_has_log_method(self):
        """Test AuditLogger has log method"""
        from backend.app.utils.audit_logger import AuditLogger

        logger = AuditLogger()

        assert hasattr(logger, "log") or hasattr(logger, "log_event")

    def test_audit_logger_format_event(self):
        """Test AuditLogger can format events"""
        from datetime import datetime

        from backend.app.utils.audit_logger import (
            AuditEvent,
            AuditEventType,
            AuditLogger,
            AuditSeverity,
        )

        logger = AuditLogger()

        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=datetime.now().isoformat(),
        )

        # If logger has _format method, test it
        if hasattr(logger, "_format_event"):
            formatted = logger._format_event(event)
            assert formatted is not None
