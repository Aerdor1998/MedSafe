"""
Root conftest.py - Sets environment variables BEFORE test collection.

This ensures that backend/app/config.py can instantiate Settings()
during module import without missing required fields.

IMPORTANT: Environment variables MUST be set at module level (not in hooks)
because Python imports happen before pytest_configure runs.
"""

import os
import sys

# Set env vars at module load time - BEFORE any other imports
# This is critical because pytest imports conftest.py early, but
# other modules may be imported even earlier during collection.
_ENV_VARS = {
    "TESTING": "true",
    "DEBUG": "true",
    "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
    "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
    "POSTGRES_PASSWORD": "test_password",
    "ENABLE_LEGACY_V1": "true",
    "PYTEST_CURRENT_TEST": "1",
}

for key, value in _ENV_VARS.items():
    os.environ.setdefault(key, value)


def pytest_configure(config):
    """
    Called after conftest.py is loaded but before test collection.
    Re-ensure env vars are set (belt and suspenders).
    """
    for key, value in _ENV_VARS.items():
        os.environ.setdefault(key, value)
