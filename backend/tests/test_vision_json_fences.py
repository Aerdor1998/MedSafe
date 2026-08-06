"""
Regression: VisionAgent deve aceitar JSON envolto em cercas markdown.

O qwen2.5-vl frequentemente responde com ```json ... ``` em volta do JSON.
Antes, `_parse_vision_response` fazia `json.loads` direto no texto cru,
caía no fallback `_extract_info_manually` e toda análise de imagem voltava
com drug_name/strength/form = "Não identificado", mesmo com o modelo tendo
extraído os dados corretamente (bug observado no upload de med-box.png).
"""

import json

import pytest

from backend.app.agents.vision import VisionAgent

PAYLOAD = {
    "drug_name": "DIPIRONA MONOIDRATADA",
    "strength": "500 mg",
    "form": "comprimido",
    "sections": [
        {
            "section_type": "posologia",
            "text": "Adultos: 1 comprimido até 4x ao dia",
            "confidence": 0.95,
            "bounding_box": [62, 407, 627, 513],
        }
    ],
}


@pytest.fixture()
def agent():
    return VisionAgent()


def _parse(agent, text: str):
    return agent._parse_vision_response({"response": text}, "sess-1")


class TestStripCodeFences:
    def test_json_fence(self, agent):
        result = _parse(agent, f"```json\n{json.dumps(PAYLOAD)}\n```")
        assert result["status"] == "completed"
        assert result["drug_name"] == "DIPIRONA MONOIDRATADA"
        assert result["strength"] == "500 mg"
        assert result["form"] == "comprimido"
        assert len(result["sections"]) == 1

    def test_plain_fence(self, agent):
        result = _parse(agent, f"```\n{json.dumps(PAYLOAD)}\n```")
        assert result["drug_name"] == "DIPIRONA MONOIDRATADA"

    def test_bare_json_still_works(self, agent):
        result = _parse(agent, json.dumps(PAYLOAD))
        assert result["drug_name"] == "DIPIRONA MONOIDRATADA"

    def test_non_json_falls_back_to_manual(self, agent):
        result = _parse(agent, "texto livre sem JSON algum")
        assert result["drug_name"] == "Não identificado"
