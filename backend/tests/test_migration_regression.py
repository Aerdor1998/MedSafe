"""
Verificações simples de flags de deprecação.
"""

from backend.app.config import settings


def test_legacy_v1_flag_present():
    assert hasattr(settings, "enable_legacy_v1")
