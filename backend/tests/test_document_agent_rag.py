"""
RAG depende de pgvector + embeddings; validado no ambiente integrado.
Placeholder para manter rastreabilidade.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="RAG exige pgvector/embeddings e DB populado; cobrir em integração dedicada."
)
