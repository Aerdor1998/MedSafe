"""
Testes para o serviço OpenFDA

NOTA: Estes testes estão temporariamente desabilitados porque referenciam
services.openfda_service que não existe no projeto atual.

Para reativar estes testes:
1. Criar services/openfda_service.py ou
2. Adaptar os testes se houver integração com OpenFDA no projeto
"""

import pytest

# TODO: Reescrever testes ou implementar OpenFDAService se necessário

pytestmark = pytest.mark.skip(reason="Serviço openfda_service não existe - testes precisam ser reescritos")
