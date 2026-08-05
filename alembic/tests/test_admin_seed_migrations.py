"""Testes herméticos das migrações 006/008 (seed e rotação da senha do admin).

Não requer banco nem passlib: testa apenas as funções puras de
detecção/derivação (validação de ADMIN_INITIAL_PASSWORD e igualdade do hash
default). Compatível com pytest e executável direto:

    python3 alembic/tests/test_admin_seed_migrations.py
"""

import importlib.util
import os
import sys
import types
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "versions"


def _stub_module(name: str, **attrs) -> None:
    """Registra um stub em sys.modules se o pacote real não estiver instalado."""
    try:
        importlib.import_module(name)
    except ImportError:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module


# As migrações importam alembic/sqlalchemy no topo, mas os helpers testados
# aqui são puros. Stubs permitem o teste rodar sem os pacotes instalados.
_stub_module("alembic", op=object())
_stub_module("sqlalchemy", text=lambda *a, **k: None)
_stub_module("sqlalchemy.dialects", postgresql=object())


def _load(filename: str):
    path = VERSIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIG_006 = _load("20260114_0900_006_add_users_and_audit.py")
MIG_008 = _load("20260804_1900_008_rotate_default_admin_password.py")


def _with_env(value, fn):
    old = os.environ.pop("ADMIN_INITIAL_PASSWORD", None)
    try:
        if value is not None:
            os.environ["ADMIN_INITIAL_PASSWORD"] = value
        return fn()
    finally:
        os.environ.pop("ADMIN_INITIAL_PASSWORD", None)
        if old is not None:
            os.environ["ADMIN_INITIAL_PASSWORD"] = old


def _raises_runtime_error(fn) -> bool:
    try:
        fn()
    except RuntimeError:
        return True
    return False


def test_006_password_required():
    assert _with_env(
        None, lambda: _raises_runtime_error(MIG_006._get_admin_initial_password)
    )
    assert _with_env(
        "", lambda: _raises_runtime_error(MIG_006._get_admin_initial_password)
    )
    assert _with_env(
        "   ", lambda: _raises_runtime_error(MIG_006._get_admin_initial_password)
    )


def test_006_password_returned_when_set():
    assert (
        _with_env("S3nh@Forte!", MIG_006._get_admin_initial_password) == "S3nh@Forte!"
    )


def test_008_password_required():
    assert _with_env(
        None, lambda: _raises_runtime_error(MIG_008._get_admin_initial_password)
    )
    assert _with_env(
        "", lambda: _raises_runtime_error(MIG_008._get_admin_initial_password)
    )


def test_008_detects_default_hash():
    assert MIG_008._needs_rotation(MIG_008.DEFAULT_SEEDED_HASH) is True
    assert (
        MIG_008._needs_rotation(
            "$2b$12$outrohashqualquerxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )
        is False
    )
    assert MIG_008._needs_rotation("") is False


def test_006_no_longer_contains_default_hash():
    source = (VERSIONS_DIR / "20260114_0900_006_add_users_and_audit.py").read_text(
        encoding="utf-8"
    )
    assert MIG_008.DEFAULT_SEEDED_HASH not in source


def test_revision_chain():
    assert MIG_006.revision == "006"
    assert MIG_008.revision == "008"
    assert MIG_008.down_revision == "007"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
