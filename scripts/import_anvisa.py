#!/usr/bin/env python3
"""Importa os Dados Abertos da ANVISA (medicamentos registrados) e gera
data/anvisa_brands.json no formato {nome_comercial_lower: principio_ativo_lower}.

Fonte oficial e gratuita:
    https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv

Uso:
    python scripts/import_anvisa.py                   # baixa e gera
    python scripts/import_anvisa.py --input dados.csv # usa CSV já baixado

Observação: o portal da ANVISA pode bloquear IPs fora do Brasil/WAF. Nesse
caso, baixe o CSV manualmente no navegador e rode com --input.
"""

import argparse
import csv
import io
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

URLS = [
    "https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv",
    "http://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv",
]
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "anvisa_brands.json"


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def download() -> str:
    for url in URLS:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (MedSafe importer)"}
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
            print(f"OK download: {url} ({len(raw) / 1e6:.1f} MB)")
            return raw.decode("cp1252", errors="replace")
        except Exception as e:  # noqa: BLE001
            print(f"Falha em {url}: {e}", file=sys.stderr)
    raise SystemExit(
        "Não foi possível baixar da ANVISA. Baixe o CSV manualmente e rode "
        "novamente com --input <arquivo>."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", help="CSV local da ANVISA (cp1252, separador ';')")
    args = ap.parse_args()

    if args.input:
        text = Path(args.input).read_text(encoding="cp1252", errors="replace")
    else:
        text = download()

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    votes: dict = {}
    total = 0
    for row in reader:
        # nomes de colunas variam entre versões do dataset
        nome = _norm(row.get("NOME_PRODUTO") or row.get("NOME_DO_PRODUTO") or "")
        ativo = _norm(row.get("PRINCIPIO_ATIVO") or row.get("PRINCÍPIO_ATIVO") or "")
        situacao = _norm(
            row.get("SITUACAO_REGISTRO") or row.get("SITUAÇÃO_REGISTRO") or ""
        )
        if not nome or not ativo:
            continue
        # manter apenas registros válidos quando a coluna existir
        if situacao and "vál" not in situacao and "val" not in situacao:
            continue
        votes.setdefault(nome, Counter())[ativo] += 1
        total += 1

    # marca → princípio ativo mais frequente (desempata variações de grafia)
    brands = {n: c.most_common(1)[0][0] for n, c in votes.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(brands, ensure_ascii=False), encoding="utf-8")
    print(f"{len(brands)} marcas ({total} registros) → {OUT}")


if __name__ == "__main__":
    main()
