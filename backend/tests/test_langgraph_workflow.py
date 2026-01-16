"""
Workflow LangGraph completo depende de DB + JWT (v2) e execução assíncrona.
Coberto por testes E2E/integração autenticada.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Workflow v2 exige JWT e infraestrutura; cobrir em e2e/autenticado."
)
