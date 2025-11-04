"""
Testes para o serviço de medicamentos

NOTA: Estes testes estão temporariamente desabilitados porque referenciam
services.drug_service que não existe no projeto atual.

Para reativar estes testes:
1. Criar services/drug_service.py com a estrutura esperada ou
2. Adaptar os testes para usar a estrutura atual do projeto
"""

import pytest

# TODO: Reescrever testes para usar a estrutura atual
# from app.services.drug_interactions import DrugInteractionService

pytestmark = pytest.mark.skip(
    reason="Serviço drug_service não existe - testes precisam ser reescritos"
)
