"""
Testes para o serviço de OCR

NOTA: Estes testes estão temporariamente desabilitados porque referenciam
services.ocr_service que não existe no projeto atual. A funcionalidade de OCR
foi implementada usando VisionAgent com qwen2.5vl.

Para reativar estes testes:
1. Criar services/ocr_service.py ou
2. Adaptar os testes para usar VisionAgent
"""

import pytest

# TODO: Reescrever testes para usar VisionAgent
# from app.agents.vision import VisionAgent

pytestmark = pytest.mark.skip(reason="Serviço ocr_service não existe - testes precisam ser reescritos")
