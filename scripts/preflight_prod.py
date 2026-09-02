#!/usr/bin/env python3
"""Fail-fast checks for a MedSafe production deployment.

The script never prints secret values. It validates only presence, minimum length,
placeholder usage, required secret files, YAML syntax, and Docker Compose structure.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SECRET_MINIMUMS = {
    "SECRET_KEY": 32,
    "JWT_SECRET": 32,
    "POSTGRES_PASSWORD": 16,
    "REDIS_PASSWORD": 16,
    "GRAFANA_PASSWORD": 16,
}


def load_env(path: Path) -> dict[str, str]:
    """Load a simple KEY=VALUE environment file without exposing values."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Return blocking errors and non-blocking deployment warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    env_path = ROOT / args.env_file
    if not env_path.is_file():
        return [f"arquivo ausente: {env_path.name}"], warnings

    env = load_env(env_path)
    for key, minimum in SECRET_MINIMUMS.items():
        value = env.get(key, "")
        if len(value) < minimum:
            errors.append(f"{key} ausente ou menor que {minimum} caracteres")

    initial_password = env.get("ADMIN_INITIAL_PASSWORD", "")
    if args.first_deploy and len(initial_password) < 12:
        errors.append("ADMIN_INITIAL_PASSWORD é obrigatória no primeiro deploy")

    origins = env.get("ALLOWED_ORIGINS", "")
    hosts = env.get("ALLOWED_HOSTS", "")
    placeholder_markers = ("seudominio", "yourdomain", "example.com")
    if not origins.startswith("https://") or "*" in origins:
        errors.append("ALLOWED_ORIGINS deve usar HTTPS e não pode conter wildcard")
    if not hosts or "*" in hosts:
        errors.append("ALLOWED_HOSTS deve listar hostnames explícitos")
    if any(
        marker in origins.lower() or marker in hosts.lower()
        for marker in placeholder_markers
    ):
        errors.append("ALLOWED_ORIGINS/ALLOWED_HOSTS ainda contêm domínio placeholder")

    secret_files = {
        "metrics": ROOT / "secrets/prometheus/metrics_auth_token",
        "alertmanager": ROOT / "secrets/alertmanager/discord_webhook_url",
    }
    for name, path in secret_files.items():
        try:
            length = len(path.read_text(encoding="utf-8").strip())
        except OSError:
            length = 0
        if length < 32:
            errors.append(f"secret {name} ausente ou vazio: {path.relative_to(ROOT)}")

    for relative_path in (
        "docker-compose.prod.yml",
        "infra/prometheus/prometheus.yml",
        ".github/workflows/ci.yml",
    ):
        path = ROOT / relative_path
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"YAML inválido em {relative_path}: {type(exc).__name__}")

    if not (ROOT / "requirements.lock").is_file():
        errors.append("requirements.lock ausente")

    if args.vercel:
        vercel = (ROOT / "frontend/vercel.json").read_text(encoding="utf-8").lower()
        if "seudominio" in vercel or "yourdomain" in vercel:
            errors.append("frontend/vercel.json ainda contém domínio placeholder")

    docker = shutil.which("docker")
    if docker:
        result = subprocess.run(
            [docker, "compose", "-f", "docker-compose.prod.yml", "config", "--quiet"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            errors.append("docker compose config falhou; revise o .env e o compose")
    else:
        warnings.append("Docker não encontrado; compose config não foi executado")

    return errors, warnings


def main() -> int:
    """Run production preflight checks and return a process exit code."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--first-deploy", action="store_true")
    parser.add_argument("--vercel", action="store_true")
    args = parser.parse_args()

    errors, warnings = validate(args)
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERRO: {error}")
    if errors:
        print(f"PREFLIGHT FALHOU ({len(errors)} erro(s))")
        return 1
    print("PREFLIGHT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
