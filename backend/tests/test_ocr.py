"""
OCR/Visão na versão atual roda via endpoint legacy /api/v1/vision/analyze.
Placeholder (exige arquivo real + backend configurado).
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Teste OCR exige fixture de imagem/PDF e backend pronto; cobrir em e2e."
)
