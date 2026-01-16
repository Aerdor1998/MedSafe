"""
HITL na versão atual é exercitado via endpoints v2 (auth-required).
Este teste é um placeholder para manter rastreabilidade.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Endpoints HITL v2 exigem JWT; cobrir em suíte autenticada."
)
