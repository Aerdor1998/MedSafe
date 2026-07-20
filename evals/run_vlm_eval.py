"""
Eval comparativo VLM — qwen2.5vl:7b vs medgemma:latest (gate da task #2).

Espelha o protocolo do VisionAgent (backend/app/langgraph_agents/vision_agent.py):
- POST {OLLAMA_HOST}/api/generate
- temperature 0.1, num_predict 2048
- system prompt idêntico (extração JSON de documentos médicos)

Casos sintéticos gerados com PIL (determinísticos):
  1. receita     — Varfarina 5mg + AAS 100mg (safety-critical: par de interação)
  2. rotulo      — Sinvastatina 40mg comprimidos revestidos
  3. negativo    — texto sem conteúdo médico (receita de bolo)

Scoring por caso: recall de fármacos esperados, captura de dosagem,
alucinação no caso negativo, latência. Gate: medgemma precisa de
score >= qwen, recall total nos casos clínicos e zero alucinação.
"""

import base64
import io
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import httpx
from PIL import Image, ImageDraw

OLLAMA = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = """You are the VisionAgent for MedSafe, a medical vision specialist.

Your role is to analyze medical document images (bulas, prescriptions, labels) and extract structured information.

EXTRACTION TARGETS:
1. Drug name (generic and brand names)
2. Concentration/strength (e.g., "500mg", "10%")
3. Pharmaceutical form (tablet, capsule, solution, etc.)

OUTPUT FORMAT:
Always respond with valid JSON containing:
{
  "drug_name": "extracted drug name",
  "strength": "concentration with units",
  "form": "pharmaceutical form",
  "all_drugs": ["list", "of", "all", "drug", "names", "found"],
  "confidence": 0.0
}

QUALITY STANDARDS:
- Accuracy > Speed: Take time to read text carefully
- Medical precision: Preserve exact dosages, units, and warnings
- Portuguese medical terminology: Respect Brazilian standards

If the image is unclear or doesn't contain medical information, set confidence < 0.5 and explain why."""

USER_PROMPT = (
    "Extraia as informações estruturadas deste documento médico. "
    "Responda APENAS com o JSON no formato especificado."
)


def make_image(lines, size=(900, 600)):
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    y = 40
    for line, big in lines:
        # fonte default do PIL; multiplicamos via resize depois para legibilidade
        d.text((40, y), line, fill="black")
        y += 34 if big else 26
    # upscale 2x para dar área de pixel suficiente ao encoder de visão
    img = img.resize((size[0] * 2, size[1] * 2), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


CASES = [
    {
        "id": "receita-varfarina-aas",
        "safety_critical": True,
        "image": make_image([
            ("CLINICA SAO LUCAS - RECEITUARIO MEDICO", True),
            ("Paciente: Jose da Silva    Data: 10/07/2026", False),
            ("", False),
            ("1) Varfarina Sodica 5mg", True),
            ("   Tomar 1 comprimido ao dia, via oral", False),
            ("", False),
            ("2) Acido Acetilsalicilico (AAS) 100mg", True),
            ("   Tomar 1 comprimido apos o almoco", False),
            ("", False),
            ("Dr. Carlos Andrade - CRM 12345", False),
        ]),
        "expected_drugs": [["varfarina"], ["acetilsalicilico", "aas", "aspirina"]],
        "expected_strengths": ["5mg", "100mg"],
    },
    {
        "id": "rotulo-sinvastatina",
        "safety_critical": False,
        "image": make_image([
            ("SINVASTATINA 40mg", True),
            ("comprimidos revestidos", False),
            ("Contem 30 comprimidos", False),
            ("USO ORAL - USO ADULTO", False),
            ("Generico - Lei 9.787/99", False),
        ]),
        "expected_drugs": [["sinvastatina"]],
        "expected_strengths": ["40mg"],
    },
    {
        "id": "negativo-receita-bolo",
        "safety_critical": False,
        "negative": True,
        "image": make_image([
            ("RECEITA DE BOLO DE CENOURA", True),
            ("3 cenouras medias raladas", False),
            ("2 xicaras de acucar", False),
            ("3 ovos e 1 xicara de oleo", False),
            ("Asse por 40 minutos a 180 graus", False),
        ]),
        "expected_drugs": [],
        "expected_strengths": [],
    },
]

KNOWN_DRUG_TOKENS = [
    "varfarina", "aas", "acetilsalicilico", "aspirina", "sinvastatina",
    "dipirona", "paracetamol", "ibuprofeno", "omeprazol", "amoxicilina",
]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower()


def call_model(model, case):
    t0 = time.monotonic()
    r = httpx.post(
        f"{OLLAMA}/api/generate",
        json={
            "model": model,
            "system": SYSTEM_PROMPT,
            "prompt": USER_PROMPT,
            "images": [case["image"]],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        },
        timeout=300.0,
    )
    r.raise_for_status()
    latency = time.monotonic() - t0
    return r.json().get("response", ""), latency


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def score_case(case, raw, parsed):
    blob = norm(raw)
    result = {"drugs_found": 0, "drugs_expected": len(case["expected_drugs"]),
              "strengths_found": 0, "hallucinated": False, "ok": True}
    for aliases in case["expected_drugs"]:
        if any(a in blob for a in aliases):
            result["drugs_found"] += 1
    for s in case["expected_strengths"]:
        if s in blob.replace(" ", ""):
            result["strengths_found"] += 1
    if case.get("negative"):
        conf = parsed.get("confidence")
        found = [t for t in KNOWN_DRUG_TOKENS if t in norm(json.dumps(parsed, ensure_ascii=False))]
        low_conf = isinstance(conf, (int, float)) and conf < 0.5
        result["hallucinated"] = bool(found) and not low_conf
        result["ok"] = not result["hallucinated"]
    else:
        result["ok"] = result["drugs_found"] == result["drugs_expected"]
    return result


def main():
    models = os.getenv("VLM_EVAL_MODELS", "qwen2.5vl:7b,medgemma:latest").split(",")
    report = {"metadata": {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "ollama": OLLAMA, "temperature": 0.1, "protocol": "VisionAgent /api/generate",
    }, "models": {}}
    for model in models:
        model = model.strip()
        entry = {"cases": [], "latency_s": [], "score": 0, "max_score": 0}
        for case in CASES:
            try:
                raw, latency = call_model(model, case)
                parsed = parse_json(raw)
                sc = score_case(case, raw, parsed)
                sc.update({"id": case["id"], "latency_s": round(latency, 1),
                           "raw_head": raw[:400]})
            except Exception as e:
                sc = {"id": case["id"], "error": str(e), "ok": False,
                      "drugs_found": 0, "drugs_expected": len(case["expected_drugs"]),
                      "strengths_found": 0, "hallucinated": False, "latency_s": None}
            entry["cases"].append(sc)
            if sc.get("latency_s"):
                entry["latency_s"].append(sc["latency_s"])
            entry["score"] += (1 if sc["ok"] else 0)
            entry["max_score"] += 1
        entry["clinical_recall"] = sum(
            c["drugs_found"] for c in entry["cases"]) / max(1, sum(c["drugs_expected"] for c in entry["cases"]))
        entry["hallucination"] = any(c.get("hallucinated") for c in entry["cases"])
        entry["latency_p50"] = sorted(entry["latency_s"])[len(entry["latency_s"]) // 2] if entry["latency_s"] else None
        report["models"][model] = entry
        print(f"[{model}] score={entry['score']}/{entry['max_score']} "
              f"recall={entry['clinical_recall']:.2f} halluc={entry['hallucination']} "
              f"p50={entry['latency_p50']}s")

    q = report["models"].get("qwen2.5vl:7b", {})
    m = report["models"].get("medgemma:latest", {})
    gate = (
        m.get("score", 0) >= q.get("score", 0)
        and m.get("clinical_recall", 0) == 1.0
        and not m.get("hallucination", True)
    )
    report["gate"] = {"migrate_to_medgemma": gate}
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(OUT_DIR, f"{ts}_vlm_ab.json")
    with open(out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"gate migrate_to_medgemma={gate} -> {out}")


if __name__ == "__main__":
    main()
