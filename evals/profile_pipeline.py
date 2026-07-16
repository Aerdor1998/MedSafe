"""Profiling de latência por chamada de LLM do pipeline (fase 3).

Intercepta BaseAgent.invoke_llm com um wrapper de timing e roda
run_analysis intacto para casos do golden set. Para cada chamada de LLM
registra: agente, duração, tamanho de entrada/saída e a fatia de
"thinking" (blocos <think> do qwen3). O resíduo não-LLM sai por
diferença contra o tempo total de parede.

Uso:
    python -m evals.profile_pipeline
    python -m evals.profile_pipeline --cases warfarina-aspirina --timeout 900
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

DEFAULT_CASES = "negativo-levotiroxina-jovem,warfarina-aspirina"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        default=DEFAULT_CASES,
        help="ids do golden set separados por vírgula (default: 1 benigno + 1 crítico)",
    )
    parser.add_argument("--golden", default=str(ROOT / "evals" / "golden_set.yaml"))
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    with open(args.golden, encoding="utf-8") as f:
        golden = yaml.safe_load(f)
    by_id = {c["id"]: c for c in golden["cases"]}
    unknown = [cid for cid in args.cases.split(",") if cid not in by_id]
    if unknown:
        print(f"ids não encontrados no golden set: {unknown}")
        return 2
    cases = [by_id[cid] for cid in args.cases.split(",")]

    from backend.app.langgraph_agents.base_agent import BaseAgent  # noqa: E402
    from backend.app.langgraph_agents.config import get_settings  # noqa: E402
    from backend.app.services.analysis_orchestrator import (
        get_orchestrator,
    )  # noqa: E402

    settings = get_settings()
    print(
        f"modelo={settings.effective_model_name} "
        f"max_reflection_cycles={settings.max_reflection_cycles}"
    )

    calls: list[dict] = []
    original_invoke = BaseAgent.invoke_llm

    def timed_invoke(self, user_message, context=None, system_prompt=None):
        t0 = time.monotonic()
        result = original_invoke(
            self, user_message, context=context, system_prompt=system_prompt
        )
        seconds = time.monotonic() - t0
        text = result or ""
        think = "".join(THINK_RE.findall(text))
        in_chars = len(user_message or "")
        if context:
            in_chars += sum(len(str(v)) for v in context.values())
        calls.append(
            {
                "agent": type(self).__name__,
                "seconds": seconds,
                "in_chars": in_chars,
                "out_chars": len(text),
                "think_chars": len(think),
            }
        )
        return result

    BaseAgent.invoke_llm = timed_invoke
    orchestrator = get_orchestrator()

    exit_code = 0
    for case in cases:
        calls.clear()
        t0 = time.monotonic()
        error = None
        try:
            await asyncio.wait_for(
                orchestrator.run_analysis(
                    patient_data=case["patient"],
                    medication_text=case["medication"],
                    session_id=f"profile-{case['id']}",
                ),
                timeout=args.timeout,
            )
        except asyncio.TimeoutError:
            error = f"timeout após {args.timeout}s"
        except Exception as e:  # noqa: BLE001 — profiling não deve abortar a suíte
            error = f"{type(e).__name__}: {e}"
        wall = time.monotonic() - t0

        print(f"\n== {case['id']} ==")
        if error:
            print(f"  ERRO: {error}")
            exit_code = 1
        llm_total = 0.0
        for c in calls:
            llm_total += c["seconds"]
            think_pct = (
                round(100 * c["think_chars"] / c["out_chars"]) if c["out_chars"] else 0
            )
            print(
                f"  {c['agent']:<18} {c['seconds']:>6.1f}s  "
                f"in={c['in_chars']:>6}  out={c['out_chars']:>6}  "
                f"think={c['think_chars']:>6} ({think_pct}%)"
            )
        residue = wall - llm_total
        llm_pct = round(100 * llm_total / wall) if wall else 0
        print(
            f"  total {wall:.1f}s | LLM {llm_total:.1f}s ({llm_pct}%) "
            f"em {len(calls)} chamadas | não-LLM {residue:.1f}s"
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
