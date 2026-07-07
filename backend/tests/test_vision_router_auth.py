"""
Regression tests: DEBUG must never widen the anonymous-access surface of
/api/v2/vision/analyze. Only allow_anonymous_analysis (default False) may
permit unauthenticated requests.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestVisionAnonymousAuthGate:
    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.vision import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @staticmethod
    def _fake_image():
        return {"file": ("receita.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}

    def test_debug_true_without_allow_anonymous_requires_auth(
        self, client, monkeypatch
    ):
        """debug=True alone must NOT bypass authentication."""
        import backend.app.routers.vision as vision_module

        monkeypatch.setattr(vision_module.app_settings, "debug", True)
        monkeypatch.setattr(
            vision_module.app_settings, "allow_anonymous_analysis", False
        )

        response = client.post("/api/v2/vision/analyze", files=self._fake_image())

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_allow_anonymous_analysis_true_permits_anonymous_access(
        self, client, monkeypatch
    ):
        """allow_anonymous_analysis=True must still permit anonymous access."""
        import backend.app.routers.vision as vision_module

        monkeypatch.setattr(vision_module.app_settings, "debug", False)
        monkeypatch.setattr(
            vision_module.app_settings, "allow_anonymous_analysis", True
        )

        response = client.post("/api/v2/vision/analyze", files=self._fake_image())

        # Must pass the auth gate; the fake PNG fails later validation (400),
        # never 401.
        assert response.status_code != 401
