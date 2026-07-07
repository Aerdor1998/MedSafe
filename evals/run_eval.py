#!/usr/bin/env python3
"""
Runner do golden set clínico — executa o MESMO pipeline da produção
(grafo LangGraph via AnalysisOrchestrator.run_analysis) contra
evals/golden_set.yaml e grava relatório JSON reprodutível.

Requisitos: stack local de pé (Ollama com o modelo + Postgres/pgvector).
NÃO roda no CI — o scoring (evals/scoring.py) é testado lá sem LLM.

Uso (host, com o docker compose do repo rodando):
    OLLAMA_HOST=http://localhost:11435 \
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
    POSTGRES_PASSWORD=... SECRET_KEY=... JWT_SECRET=... \
    python evals/run_eval.py [--limit N] [--case ID] [--timeout 300]

Troca de modelo = trocar OLLAMA_LLM no ambiente e rodar de novo; compare
os JSONs em evals/results/. O gate para adotar um modelo novo é
safety_critical_recall igual ou melhor E false_alarm_rate igual ou melhor
que o baseline.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.scoring import (  # noqa: E402
    CheckResult,
    score_case,
    summarize,
    validate_case,
)


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _serialize_checks(checks: list[CheckResult]) -> list[dict]:
    return [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in checks]


async def run_case(orchestrator, case: dict, timeout: float) -> dict:
    started = time.monotonic()
    try:
        result = await asyncio.wait_for(
            orchestrator.run_analysis(
                patient_data=case["patient"],
                medication_text=case["medication"],
                session_id=f"eval-{case['id']}",
            ),
            timeout=timeout,
        )
        error = None
    except asyncio.TimeoutError:
        result, error = {}, f"timeout após {timeout}s"
    except Exception as e:  # noqa: BLE001 — eval não pode abortar a suíte
        result, error = {}, f"{type(e).__name__}: {e}"

    duration = time.monotonic() - started
    checks = score_case(case, result) if error is None else []

    risk = result.get("risk_level")
    if hasattr(risk, "value"):
        risk = risk.value

    return {
        "case": case,
        "checks": checks,
        "error": error,
        "observed": {
            "risk_level": risk,
            "n_interactions": len(result.get("interactions") or []),
            "n_contraindications": len(result.get("contraindications") or []),
            "requires_human_review": bool(result.get("requires_human_review", False)),
            "confidence_score": result.get("confidence_score"),
            "duration_seconds": round(duration, 1),
        },
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="MedSafe golden set eval")
    parser.add_argument("--golden", default=str(ROOT / "evals" / "golden_set.yaml"))
    parser.add_argument("--case", default=None, help="rodar apenas o caso com este id")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=300.0, help="por caso (s)")
    parser.add_argument("--output-dir", default=str(ROOT / "evals" / "results"))
    args = parser.parse_args()

    with open(args.golden, encoding="utf-8") as f:
        golden = yaml.safe_load(f)
    cases = golden["cases"]

    schema_errors = {
        c.get("id", f"<caso {i}>"): validate_case(c)
        for i, c in enumerate(cases)
        if validate_case(c)
    }
    if schema_errors:
        print(f"Golden set inválido: {json.dumps(schema_errors, indent=2)}")
        return 2

    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"Caso '{args.case}' não encontrado")
            return 2
    if args.limit:
        cases = cases[: args.limit]

    # Imports pesados só depois de validar o golden set (exigem env/DB).
    from backend.app.langgraph_agents.config import get_settings
    from backend.app.services.analysis_orchestrator import get_orchestrator

    settings = get_settings()
    orchestrator = get_orchestrator()

    print(
        f"Rodando {len(cases)} casos | modelo={settings.effective_model_name} "
        f"| temp={settings.ollama_temperature} | timeout/caso={args.timeout}s"
    )

    scored = []
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {case['id']} — {case['medication']}", flush=True)
        item = await run_case(orchestrator, case, args.timeout)
        scored.append(item)

        obs = item["observed"]
        if item["error"]:
            print(f"   ERRO: {item['error']} ({obs['duration_seconds']}s)")
        else:
            for check in item["checks"]:
                mark = "PASS" if check.passed else "FAIL"
                print(f"   [{mark}] {check.name}: {check.detail}")
            print(
                f"   risco={obs['risk_level']} interações={obs['n_interactions']} "
                f"review={obs['requires_human_review']} ({obs['duration_seconds']}s)"
            )

    summary = summarize(scored)

    report = {
        "metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model": settings.effective_model_name,
            "temperature": settings.ollama_temperature,
            "git_commit": _git_commit(),
            "golden_set": str(Path(args.golden).name),
            "n_cases": len(cases),
            "timeout_per_case": args.timeout,
        },
        "summary": summary,
        "cases": [
            {
                "id": item["case"]["id"],
                "safety_critical": bool(item["case"].get("safety_critical")),
                "negative": bool(item["case"].get("negative")),
                "error": item["error"],
                "observed": item["observed"],
                "checks": _serialize_checks(item["checks"]),
                "passed": item["error"] is None
                and all(c.passed for c in item["checks"]),
            }
            for item in scored
        ],
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_slug = settings.effective_model_name.replace(":", "_").replace("/", "_")
    out_path = out_dir / f"{stamp}_{model_slug}.json"
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print(
        f"Casos: {summary['passed_cases']}/{summary['total_cases']} aprovados | "
        f"GATE safety-critical: {summary['safety_critical_passed']}/"
        f"{summary['safety_critical_total']} | "
        f"falso alarme: {summary['negative_failed']}/{summary['negative_total']}"
    )
    print(f"Relatório: {out_path}")
    print("GATE OK" if summary["gate_ok"] else "GATE REPROVADO")
    return 0 if summary["gate_ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
