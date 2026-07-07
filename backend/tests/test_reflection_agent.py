"""
Unit tests for ReflectionAgent response parsing.

O ReflectionAgent é a garantia de qualidade da análise clínica. O parser
antigo casava keywords em INGLÊS contra respostas em PORTUGUÊS e, sem
nenhum sinal reconhecido, assumia PASS — ou seja, uma crítica ilegível
aprovava silenciosamente a análise médica. Estes testes cobrem o novo
contrato:

1. Linha estruturada `CRITIQUE_LEVEL: <NIVEL>` é a fonte primária.
2. Frases em PT-BR e EN funcionam como fallback.
3. Resposta irreconhecível → MEDIUM (nunca PASS silencioso).
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.app.langgraph_agents.state import CritiqueLevel


def _make_agent():
    """Instancia ReflectionAgent com LLM/settings/logger mockados."""
    with patch(
        "backend.app.langgraph_agents.base_agent.ChatOllama"
    ) as mock_ollama, patch(
        "backend.app.langgraph_agents.base_agent.get_settings"
    ) as mock_settings, patch(
        "backend.app.langgraph_agents.base_agent.get_agent_logger"
    ) as mock_logger:
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.1
        settings.ollama_max_tokens = 2048
        settings.effective_model_name = "qwen3:8b"
        settings.ollama_timeout = 300
        settings.max_reflection_cycles = 3
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()

        from backend.app.langgraph_agents.reflection_agent import ReflectionAgent

        return ReflectionAgent()


class TestStructuredCritiqueLevel:
    """A linha CRITIQUE_LEVEL é a fonte primária e determinística."""

    @pytest.mark.parametrize(
        "tag,expected",
        [
            ("CRITICAL", CritiqueLevel.CRITICAL),
            ("HIGH", CritiqueLevel.HIGH),
            ("MEDIUM", CritiqueLevel.MEDIUM),
            ("LOW", CritiqueLevel.LOW),
            ("PASS", CritiqueLevel.PASS),
        ],
    )
    def test_tagged_line_is_parsed(self, tag, expected):
        agent = _make_agent()
        response = f"CRITIQUE_LEVEL: {tag}\n\nAnálise revisada em detalhe."

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == expected

    def test_tagged_line_case_insensitive_and_mid_text(self):
        agent = _make_agent()
        response = "Resumo da revisão.\ncritique_level: high\n- Falta interação X"

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.HIGH

    def test_tag_wins_over_conflicting_prose(self):
        """O tag estruturado prevalece sobre frases soltas no texto."""
        agent = _make_agent()
        response = (
            "CRITIQUE_LEVEL: CRITICAL\n"
            "A análise está quase completa, mas a severidade da interação "
            "warfarina+aspirina foi subestimada — erro perigoso."
        )

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.CRITICAL


class TestPortugueseFallback:
    """Sem tag, frases em PT-BR (idioma real das respostas) são reconhecidas."""

    def test_nivel_de_critica_critico(self):
        agent = _make_agent()
        response = "Nível de crítica: CRÍTICO\nErros perigosos identificados."

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.CRITICAL

    def test_erros_perigosos_sem_nivel_explicito(self):
        agent = _make_agent()
        response = (
            "A revisão encontrou erros perigosos que podem prejudicar o paciente."
        )

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.CRITICAL

    def test_lacunas_significativas(self):
        agent = _make_agent()
        response = "Há lacunas significativas: a interação com lítio não foi avaliada."

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.HIGH

    def test_analise_precisa_e_completa_passa(self):
        agent = _make_agent()
        response = (
            "Nível de crítica: PASS. A análise está precisa e completa; "
            "todas as interações foram corretamente identificadas."
        )

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.PASS


class TestEnglishFallbackStillWorks:
    """Compatibilidade: frases EN do parser antigo continuam reconhecidas."""

    def test_critical_issues_found(self):
        agent = _make_agent()
        response = "Critical issues found: missing interaction severity."

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.CRITICAL

    def test_analysis_is_accurate(self):
        agent = _make_agent()
        response = "The analysis is accurate and complete. No issues found."

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.PASS


class TestSafeDefault:
    """Resposta irreconhecível NUNCA aprova silenciosamente (era PASS)."""

    def test_unrecognizable_response_defaults_to_medium(self):
        agent = _make_agent()
        response = "Lorem ipsum dolor sit amet, resposta fora de formato."

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.MEDIUM

    def test_empty_response_defaults_to_medium(self):
        agent = _make_agent()

        result = agent._parse_reflection_response("")

        assert result["critique_level"] == CritiqueLevel.MEDIUM

    def test_issues_without_level_upgrade_to_medium(self):
        """Regra existente preservada: bullets de problemas sem nível → MEDIUM."""
        agent = _make_agent()
        response = (
            "Revisão concluída.\n"
            "- A dosagem recomendada não considera a função renal do paciente\n"
            "- Falta citar a fonte da interação warfarina+aspirina"
        )

        result = agent._parse_reflection_response(response)

        assert result["critique_level"] == CritiqueLevel.MEDIUM
        assert len(result["issues"]) == 2

    def test_unparseable_triggers_refinement_on_first_cycle(self):
        """MEDIUM (default seguro) deve refinar nos ciclos iniciais."""
        agent = _make_agent()
        reflection = agent._parse_reflection_response("resposta ilegível qualquer")
        state = {"refinement_count": 0}

        assert agent._should_refine(state, reflection) is True


class TestPromptRequestsStructuredTag:
    """O prompt de reflexão deve exigir a linha CRITIQUE_LEVEL."""

    def test_reflection_prompt_mentions_tag(self):
        agent = _make_agent()
        captured = {}

        def _fake_invoke(prompt, context=None, system_prompt=None):
            captured["prompt"] = prompt
            return "CRITIQUE_LEVEL: PASS\nTudo certo."

        agent.invoke_llm = _fake_invoke
        state = {
            "medication_text": "aspirina",
            "patient_data": {"conditions": []},
            "interactions": [
                {"drug1": "a", "drug2": "b", "severity": "low", "description": "x"}
            ],
            "contraindications": [],
            "risk_level": "low",
            "confidence_score": 0.9,
            "refinement_count": 0,
        }

        critique = agent._perform_reflection(state)

        assert "CRITIQUE_LEVEL" in captured["prompt"]
        assert critique["critique_level"] == CritiqueLevel.PASS
