"""
Unit tests for the PHI/PII log redaction filter.

Regressão crítica de produção: o PHIRedactionFilter (sempre ativo em
produção para LGPD) convertia args numéricos de LogRecord em strings —
`(0,)` virava `('0',)` — quebrando qualquer log %-style com `%d`/`%f` no
app inteiro. O logging engolia o TypeError e a linha de log era PERDIDA
("--- Logging error ---"), incluindo trilhas de auditoria.
"""

import logging

from backend.app.utils.log_redaction import PHIRedactionFilter, redact_sensitive_data


def _make_record(msg, args=None):
    return logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


class TestNumericArgsPreserved:
    """Args numéricos devem passar intactos pelo filtro."""

    def test_int_args_survive_and_percent_d_formats(self):
        f = PHIRedactionFilter(enabled=True)
        record = _make_record("resposta sem nivel (len=%d)", args=(0,))

        assert f.filter(record) is True
        assert record.args == (0,)
        # getMessage() é onde o TypeError explodia antes do fix
        assert record.getMessage() == "resposta sem nivel (len=0)"

    def test_float_and_bool_args_survive(self):
        f = PHIRedactionFilter(enabled=True)
        record = _make_record("score=%.2f ok=%s", args=(0.85, True))

        assert f.filter(record) is True
        assert record.args == (0.85, True)
        assert record.getMessage() == "score=0.85 ok=True"

    def test_mixed_args_only_strings_redacted(self):
        f = PHIRedactionFilter(enabled=True)
        record = _make_record("user cpf=%s tentativas=%d", args=("123.456.789-01", 3))

        assert f.filter(record) is True
        assert record.args[0] == "[CPF_REDACTED]"
        assert record.args[1] == 3
        assert record.getMessage() == "user cpf=[CPF_REDACTED] tentativas=3"


class TestStringRedactionStillWorks:
    """O fix não pode enfraquecer a redação de PHI em strings."""

    def test_cpf_in_message_is_redacted(self):
        f = PHIRedactionFilter(enabled=True)
        record = _make_record("paciente cpf 123.456.789-01 processado")

        assert f.filter(record) is True
        assert "[CPF_REDACTED]" in record.getMessage()
        assert "123.456.789-01" not in record.getMessage()

    def test_email_is_redacted(self):
        assert (
            redact_sensitive_data("contato: fulano@example.com")
            == "contato: [EMAIL_REDACTED]"
        )

    def test_dict_args_values_still_redacted(self):
        # Um único dict em args vira o próprio record.args (formato %(chave)s);
        # o filtro redata os VALORES por padrão de PHI.
        f = PHIRedactionFilter(enabled=True)
        record = _make_record("evento cpf=%(cpf)s", args=({"cpf": "123.456.789-01"},))

        assert f.filter(record) is True
        assert record.getMessage() == "evento cpf=[CPF_REDACTED]"
