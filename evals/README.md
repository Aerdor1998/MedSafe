# Evals — Golden Set Clínico

Harness de avaliação do pipeline clínico (grafo LangGraph completo, o
mesmo caminho de código da produção). É o **gate obrigatório para trocar
modelo ou prompt**: nada muda de LLM/VLM sem rodar isto antes e depois.

## Arquivos

| Arquivo | O quê |
|---|---|
| `golden_set.yaml` | Casos sintéticos (sem PHI) com resposta esperada — em git |
| `scoring.py` | Scoring determinístico (testado no CI sem LLM) |
| `run_eval.py` | Runner local (exige Ollama + Postgres de pé) |
| `results/` | Relatórios JSON por execução — **fora do git** |

## Como rodar (local)

Com o stack do repo rodando (`./scripts/docker-start.sh` ou `docker compose up -d`):

```bash
# Env mínimo apontando para os serviços do compose (portas do host)
export OLLAMA_HOST=http://localhost:11435
export POSTGRES_HOST=localhost POSTGRES_PORT=5433
export POSTGRES_PASSWORD=<do seu .env>
export SECRET_KEY=<do seu .env> JWT_SECRET=<do seu .env>

python evals/run_eval.py                 # suíte completa
python evals/run_eval.py --limit 3       # smoke
python evals/run_eval.py --case warfarina-aspirina
```

Cada execução grava `evals/results/<timestamp>_<modelo>.json` com
metadados de reprodutibilidade (modelo efetivo, temperatura, commit git).

## Critério de gate para troca de modelo

1. Rode o baseline com o modelo atual (`OLLAMA_LLM=qwen3:8b`).
2. Rode com o candidato (ex.: `OLLAMA_LLM=<medgemma-4b>`; o modelo precisa
   estar puxado no Ollama).
3. O candidato só é adotado se, comparando os dois JSONs:
   - `safety_critical_recall` **igual ou melhor** (casos `safety_critical:
     true` são inegociáveis — exit code 1 se qualquer um falhar), **e**
   - `false_alarm_rate` **igual ou melhor** (superproteção gera alert
     fatigue em clínica — também é dano).

## Histórico de comparações

| Data | Baseline | Candidato | Decisão |
|---|---|---|---|
| 2026-07-12 | qwen3:8b — 17/17, recall 1.0, falso alarme 0.0, p50 103s, máx 387s | qwen3:14b — 6/6 acertos nos casos que completaram, mas 405–541s/caso com VRAM saturada (15,7/16 GB na RTX 4070 Ti SUPER) | **Mantido qwen3:8b.** 14b inviável neste hardware: latência acima do timeout de produção (300s). Reavaliar só com quantização mais agressiva ou GPU maior. |

Lição operacional: dois modelos residentes (14b + 8b) estouraram a VRAM e
**travaram o Ollama** no meio da rodada — em GPU de 16 GB, garanta que só o
candidato esteja carregado (`ollama ps`) antes de rodar a suíte.

| Data | Baseline | Candidato | Decisão |
|---|---|---|---|
| 2026-07-12 | `MAX_REFLECTION_CYCLES=3` (default) — 17/17, p50 103s, máx 387s, média 132s | `MAX_REFLECTION_CYCLES=1` — 16/17 (gate binário OK, mas `clopidogrel-omeprazol` caiu para `low`; esperado ≥ `medium`), p50 112s, máx 246s, média 110s | **Mantido default 3.** Cortar reflexão só melhora a cauda (máx −37%); a mediana não muda — o custo base do pipeline sem nenhum ciclo de reflexão já é 28–94s. Latência de produção deve ser atacada no caminho base (retrieval + passes de LLM) e em UX assíncrona, não na reflexão, que é o que protege a severidade graduada. |
| 2026-07-13 | qwen3:8b (`20260712T111022Z`) — 17/17, recall 1.0, falso alarme 0.0, média 131s, p50 103s, máx 387s, reflexão média 2.24 (cap 3 em 12/17 casos) | medgemma:latest (`20260713T023227Z`) — 17/17, recall 1.0, falso alarme 0.0, média 106s (−19%), p50 119s (+16%), máx 178s (−54%), reflexão média 2.29 (cap 3 em 13/17 casos) | **Gate atendido para adoção** (recall e falso alarme iguais). Vantagem decisiva na cauda: máx 178s cabe no timeout de produção de 300s, que a baseline estourava (387s). Contra: p50 16% pior e reflexão continua batendo no cap na maioria dos casos. Troca do default pendente de confirmação. |

## Notas

- Boa parte das expectativas cobre o caminho **determinístico** (CSV,
  regras clínicas, classifier) — mudanças de modelo afetam sobretudo
  severidade via LLM, reflexão e confiança; os dois juntos é o que o
  gate mede.
- Timeout por caso: 300s (`--timeout`). Erro/timeout conta como falha.
- Para adicionar um caso: siga o schema comentado no topo do
  `golden_set.yaml`; o CI valida schema, ids únicos e resolução dos
  nomes de medicamentos (`backend/tests/test_eval_scoring.py`).
