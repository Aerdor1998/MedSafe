"""
Unit tests for the data retention worker.

Cobre `_log_retention_action`, garantindo que o audit log de retenção LGPD
(Art. 37) grava apenas colunas que realmente existem no modelo `AuditLog`
(ver backend/app/db/user_models.py), já que um INSERT com colunas erradas
falhava silenciosamente e nenhuma exclusão LGPD era auditada.
"""

from unittest.mock import MagicMock, patch

from backend.app.db.user_models import AuditLog
from backend.app.workers.data_retention_worker import (
    RetentionPolicy,
    _log_retention_action,
)


def _make_policy(**overrides) -> RetentionPolicy:
    defaults = dict(
        table_name="triage",
        retention_days=90,
        date_column="created_at",
        soft_delete=True,
        anonymize_columns=["notes"],
    )
    defaults.update(overrides)
    return RetentionPolicy(**defaults)


class TestLogRetentionAction:
    """Tests for _log_retention_action's audit INSERT."""

    def test_uses_only_real_auditlog_columns(self):
        """
        Os parâmetros do INSERT devem corresponder a colunas reais do modelo
        AuditLog (não actor_id/actor_type, que não existem), e event_category
        (NOT NULL no modelo) deve ser fornecido.
        """
        db = MagicMock()
        policy = _make_policy()

        with patch(
            "backend.app.workers.data_retention_worker._table_has_column",
            return_value=True,
        ):
            _log_retention_action(db, "soft_delete", "triage", 5, policy)

        db.execute.assert_called_once()
        sql_arg, params = db.execute.call_args[0]

        sql_text = str(sql_arg)
        assert "actor_id" not in sql_text
        assert "actor_type" not in sql_text
        assert "event_category" in sql_text
        assert "user_id" in sql_text

        # As colunas usadas no bind devem existir de fato no modelo AuditLog.
        model_columns = {c.name for c in AuditLog.__table__.columns}
        for key in params:
            assert key in model_columns, f"Coluna '{key}' não existe em AuditLog"

        assert params["event_category"] == "lgpd"
        assert params["action"] == "soft_delete"
        assert params["event_type"] == "data_retention_soft_delete"
        assert params["resource_type"] == "triage"

        # Garantir que os valores realmente instanciam um AuditLog válido
        # (ou seja, os nomes de coluna batem com os kwargs aceitos pelo model).
        audit_log = AuditLog(
            event_type=params["event_type"],
            event_category=params["event_category"],
            severity=params["severity"],
            resource_type=params["resource_type"],
            action=params["action"],
            details=params["details"],
        )
        assert audit_log.event_category == "lgpd"
        assert audit_log.action == "soft_delete"

    def test_skips_when_audit_table_missing(self):
        """Se audit_logs não existe, não deve tentar executar INSERT."""
        db = MagicMock()
        policy = _make_policy()

        with patch(
            "backend.app.workers.data_retention_worker._table_has_column",
            return_value=False,
        ):
            _log_retention_action(db, "soft_delete", "triage", 5, policy)

        db.execute.assert_not_called()

    def test_logs_error_when_insert_fails(self):
        """
        Falha ao gravar auditoria não deve ser engolida silenciosamente:
        deve chamar logger.error (não apenas warning, e não `pass`).
        """
        db = MagicMock()
        db.execute.side_effect = Exception("boom")
        policy = _make_policy()

        with patch(
            "backend.app.workers.data_retention_worker._table_has_column",
            return_value=True,
        ), patch("backend.app.workers.data_retention_worker.logger") as mock_logger:
            _log_retention_action(db, "hard_delete", "analysis_jobs", 3, policy)

        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert "analysis_jobs" in error_message
