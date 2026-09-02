"""Regression tests for production-only security boundaries."""

from pathlib import Path
from types import SimpleNamespace

import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader que aceita as tags de merge do Compose (!override, !reset).

    São sintaxe oficial do Compose v2.24+ para substituir (em vez de acumular)
    um campo vindo de outro arquivo. O SafeLoader puro aborta ao encontrá-las.
    """


def _compose_tag(loader, node):
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return loader.construct_scalar(node)


for _tag in ("!override", "!reset"):
    _ComposeLoader.add_constructor(_tag, _compose_tag)


def _request(headers=None, client_host="203.0.113.9") -> StarletteRequest:
    raw_headers = [
        (name.lower().encode(), value.encode())
        for name, value in (headers or {}).items()
    ]
    return StarletteRequest(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": (client_host, 12345),
        }
    )


def test_unvalidated_api_key_cannot_rotate_rate_limit_identity(monkeypatch):
    from backend.app.middleware.rate_limit import get_rate_limit_key

    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    request = _request({"X-API-Key": "attacker-controlled"})

    assert get_rate_limit_key(request) == "ip:203.0.113.9"


def test_proxy_ip_headers_require_explicit_trust(monkeypatch):
    from backend.app.middleware.rate_limit import get_rate_limit_key

    request = _request({"CF-Connecting-IP": "198.51.100.7"})

    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    assert get_rate_limit_key(request) == "ip:203.0.113.9"

    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    assert get_rate_limit_key(request) == "ip:198.51.100.7"


def _metrics_client(monkeypatch, settings) -> TestClient:
    import backend.app.middleware.prometheus as prometheus_module

    monkeypatch.setattr(prometheus_module, "settings", settings)
    app = FastAPI()

    @app.get("/metrics")
    async def metrics(request: Request):
        return await prometheus_module.metrics_endpoint(request)

    return TestClient(app)


def test_metrics_fail_closed_without_production_secret(monkeypatch, tmp_path):
    client = _metrics_client(
        monkeypatch,
        SimpleNamespace(
            enable_metrics=True,
            is_production=True,
            metrics_auth_token_file=str(tmp_path / "missing"),
        ),
    )

    assert client.get("/metrics").status_code == 503


def test_metrics_require_matching_bearer_token_in_production(monkeypatch, tmp_path):
    token = "a" * 48
    token_file = tmp_path / "metrics-token"
    token_file.write_text(token, encoding="utf-8")
    client = _metrics_client(
        monkeypatch,
        SimpleNamespace(
            enable_metrics=True,
            is_production=True,
            metrics_auth_token_file=str(token_file),
        ),
    )

    assert client.get("/metrics").status_code == 401
    response = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_metrics_remain_available_without_token_outside_production(monkeypatch):
    client = _metrics_client(
        monkeypatch,
        SimpleNamespace(
            enable_metrics=True,
            is_production=False,
            metrics_auth_token_file=None,
        ),
    )

    assert client.get("/metrics").status_code == 200


def test_production_compose_gates_application_on_migrations_and_metrics_secret():
    root = Path(__file__).resolve().parents[2]
    compose = yaml.load(
        (root / "docker-compose.prod.yml").read_text(encoding="utf-8"),
        Loader=_ComposeLoader,
    )
    services = compose["services"]

    assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
    for service_name in ("api", "worker", "retention-worker"):
        assert services[service_name]["depends_on"]["migrate"]["condition"] == (
            "service_completed_successfully"
        )

    assert "metrics_auth_token" in services["api"]["secrets"]
    assert "metrics_auth_token" in services["prometheus"]["secrets"]
    assert services["nginx"]["profiles"] == ["tls"]


def test_health_router_does_not_shadow_canonical_metrics_route():
    from backend.app.routers.health import router

    assert "/metrics" not in {route.path for route in router.routes}
