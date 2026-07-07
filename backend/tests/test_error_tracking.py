"""
Unit tests for error tracking setup (Sentry-compatible, self-hosted).

Contrato:
1. Sem SENTRY_DSN → no-op (retorna False, não inicializa SDK).
2. Com DSN → inicializa com guardas de PHI/LGPD OBRIGATÓRIOS:
   send_default_pii=False e include_local_variables=False (variáveis
   locais de stack frames carregam dados de paciente neste app).
3. sentry-sdk ausente → degrada graciosamente (False, sem exceção).
"""

import sys
from unittest.mock import MagicMock, patch

from backend.app.utils.error_tracking import setup_error_tracking


def _settings(dsn=None, traces=0.0):
    s = MagicMock()
    s.sentry_dsn = dsn
    s.sentry_traces_sample_rate = traces
    s.environment = "development"
    s.app_version = "1.0.0"
    return s


class TestNoDsn:
    def test_returns_false_and_does_not_init(self):
        fake_sdk = MagicMock()
        with patch.dict(sys.modules, {"sentry_sdk": fake_sdk}):
            assert setup_error_tracking(_settings(dsn=None)) is False
            assert setup_error_tracking(_settings(dsn="")) is False

        fake_sdk.init.assert_not_called()


class TestWithDsn:
    def test_initializes_with_phi_guards(self):
        fake_sdk = MagicMock()
        with patch.dict(sys.modules, {"sentry_sdk": fake_sdk}):
            result = setup_error_tracking(
                _settings(dsn="http://key@glitchtip.local:8090/1", traces=0.1)
            )

        assert result is True
        fake_sdk.init.assert_called_once()
        kwargs = fake_sdk.init.call_args.kwargs
        assert kwargs["dsn"] == "http://key@glitchtip.local:8090/1"
        assert kwargs["environment"] == "development"
        assert kwargs["release"] == "medsafe@1.0.0"
        assert kwargs["traces_sample_rate"] == 0.1
        # Guardas de PHI/LGPD — nunca relaxar sem revisão de compliance
        assert kwargs["send_default_pii"] is False
        assert kwargs["include_local_variables"] is False


class TestSdkMissing:
    def test_returns_false_without_raising(self):
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            assert setup_error_tracking(_settings(dsn="http://k@h/1")) is False
