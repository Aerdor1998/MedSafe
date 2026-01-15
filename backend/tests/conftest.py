"""
Configuração global para testes pytest (versão LangGraph)
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Garantir que o diretório raiz do projeto esteja no PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def app():
    """
    FastAPI app in-process (ASGI) for unit/integration tests.

    IMPORTANT: We do NOT require an external server running on localhost.
    """
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-minimum-32-characters-long")
    os.environ.setdefault("POSTGRES_PASSWORD", "test_password")

    # Import the already-instantiated app to avoid double initialization
    from backend.app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app):
    """Synchronous TestClient for FastAPI endpoints."""
    with TestClient(app) as c:
        yield c
