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

## Notas

- Boa parte das expectativas cobre o caminho **determinístico** (CSV,
  regras clínicas, classifier) — mudanças de modelo afetam sobretudo
  severidade via LLM, reflexão e confiança; os dois juntos é o que o
  gate mede.
- Timeout por caso: 300s (`--timeout`). Erro/timeout conta como falha.
- Para adicionar um caso: siga o schema comentado no topo do
  `golden_set.yaml`; o CI valida schema, ids únicos e resolução dos
  nomes de medicamentos (`backend/tests/test_eval_scoring.py`).
