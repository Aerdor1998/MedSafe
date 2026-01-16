"""
DEPRECATED: Legacy services re-export module.

This module existed for backwards compatibility but is no longer needed.
Import services directly from backend.app.services instead.

Example:
    from backend.app.services.openfda_service import OpenFDAService
"""

# Maintain backwards compatibility for any code still importing from here
try:
    from backend.app.services.openfda_service import OpenFDAService
except ImportError:
    OpenFDAService = None
