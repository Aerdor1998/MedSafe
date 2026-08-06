"""Contrato: risk_level na resposta da API é sempre membro do enum ou 'unknown'."""
from backend.app.langgraph_agents.state import RiskLevel
from backend.app.routers.langgraph import serialize_risk_level


class TestSerializeRiskLevel:
    def test_enum_members_serialize_to_lowercase_value(self):
        assert serialize_risk_level(RiskLevel.CRITICAL) == "critical"
        assert serialize_risk_level(RiskLevel.HIGH) == "high"
        assert serialize_risk_level(RiskLevel.MEDIUM) == "medium"
        assert serialize_risk_level(RiskLevel.LOW) == "low"

    def test_valid_plain_strings_pass_through(self):
        for value in ("critical", "high", "medium", "low"):
            assert serialize_risk_level(value) == value

    def test_anything_else_degrades_explicitly_to_unknown(self):
        for bad in (None, "", "RiskLevel.LOW", "LOW", "baixo", 7.5, object()):
            assert serialize_risk_level(bad) == "unknown"
