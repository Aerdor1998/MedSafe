# Runbook de Produção — MedSafe

Arquitetura do piloto: o backend roda nesta máquina via `docker-compose.prod.yml`, é
exposto à internet por um Cloudflare Tunnel, e o frontend estático fica no Vercel
encaminhando `/api/*` para a URL do túnel.

Todos os comandos assumem `cwd` na raiz do repo (`medsafe/`), salvo indicação contrária.

> **Estado em 2026-07-25.** Este runbook foi reescrito depois de uma auditoria que
> encontrou vários comandos da versão anterior que falhavam como escritos. Se algo aqui
> não bater com a realidade, o runbook está errado — corrija-o no mesmo commit.

---

## 0. Pré-requisitos para chamar isto de "produção"

Marque tudo antes de atender paciente real:

- [ ] `.env` preenchido com secrets gerados (seção 1) — **incluindo `ALLOWED_HOSTS` com o hostname público real**
- [ ] Secrets de métricas e Alertmanager criados em arquivo (seções 1 e 7)
- [ ] Ollama nativo no ar com `medgemma:latest` e `qwen2.5vl:7b` (seção 2)
- [ ] Named tunnel com DNS fixo (seção 4) — quick tunnel **não** serve para produção
- [ ] Senha do admin semeado trocada (seção 3)
- [ ] Um restore de verdade testado (seção 8)
- [ ] Entrega de alertas configurada no Alertmanager (seção 7)
- [ ] `SENTRY_DSN` preenchido (seção 7)
- [ ] Gate clínico verde no commit que vai subir (seção 9)
- [ ] `python scripts/preflight_prod.py --first-deploy --vercel` termina com `PREFLIGHT OK`
- [ ] Ambiente GitHub `staging` possui `E2E_BASE_URL`, `E2E_EMAIL` e `E2E_PASSWORD`

---

## 1. Configuração inicial (uma vez)

```bash
cp env.prod.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'   # gere cada secret
```

Preencha no `.env`: `SECRET_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
`ADMIN_INITIAL_PASSWORD`, `GRAFANA_PASSWORD`, `PGADMIN_PASSWORD`, `ALLOWED_ORIGINS`,
`ALLOWED_HOSTS`.

Crie também a credencial de scrape; ela não fica no `.env` nem no Git:

```bash
mkdir -p secrets/prometheus
python3 -c 'import secrets; print(secrets.token_urlsafe(48))' \
  > secrets/prometheus/metrics_auth_token
chmod 600 secrets/prometheus/metrics_auth_token
```

**`ALLOWED_HOSTS` é obrigatório e o compose recusa subir sem ele.** Motivo: o
`TrustedHostMiddleware` compara o header `Host`; se o hostname público não estiver na
lista, *toda* requisição vinda do túnel volta `400 Invalid host header` — com os
containers de pé e "saudáveis". Inclua o host do túnel e o domínio final, por exemplo:

```
ALLOWED_HOSTS=api.seudominio.com,localhost,127.0.0.1
ALLOWED_ORIGINS=https://app.seudominio.com
```

Enquanto estiver em quick tunnel, `*.trycloudflare.com` funciona, mas é permissivo
(aceita qualquer túnel do Cloudflare) — troque pelo hostname exato assim que houver
domínio.

O que **não** precisa estar certo no `.env`: `ENVIRONMENT`, `DEBUG` e
`ALLOW_ANONYMOUS_ANALYSIS`. O `docker-compose.prod.yml` fixa os três
(`production` / `false` / `false`) direto no serviço, justamente para que a config de
desenvolvimento não vaze para produção.

---

## 2. Ollama (host nativo, GPU)

A stack usa o Ollama **nativo do WSL2**, não o container — o Docker local não tem o
runtime nvidia. Os serviços `api`/`worker` já apontam para
`http://host.docker.internal:11434`.

```bash
pgrep -a ollama || (nohup ollama serve > /tmp/ollama.log 2>&1 &)
curl -fsS http://localhost:11434/api/tags | head -c 200   # deve listar os modelos
ollama list | grep -E 'medgemma|qwen2.5vl'
```

> Em 2026-07-25 o Ollama estava **fora do ar** enquanto `/healthz` respondia
> `healthy` — toda análise clínica falharia em silêncio. Por isso `/healthz` agora
> reporta `degraded` quando o Ollama some, e existe o alerta `OllamaDown`. Confira o
> Ollama antes de considerar a stack no ar.

O container `ollama` do compose está atrás do profile `gpu-container` e **não sobe**
por padrão. Não o inclua no `up` (era o erro do runbook anterior: listar `ollama`
ativava o profile e falhava na reserva de GPU).

---

## 3. Subir a stack

```bash
python3 scripts/preflight_prod.py --first-deploy --vercel
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps -a
docker compose -f docker-compose.prod.yml logs migrate
```

`migrate` deve terminar com código 0 antes de `api`, `worker` e
`retention-worker` iniciarem. Em instalação nova, a revisão 006 falha de propósito
se `ADMIN_INITIAL_PASSWORD` estiver vazia; não existe senha pública de fallback.

Serviços e para que servem:

| Serviço | Papel |
|---|---|
| `db`, `redis` | Estado. Portas publicadas só em `127.0.0.1`. |
| `migrate` | Gate one-shot que executa `alembic upgrade head` antes da aplicação. |
| `api` | FastAPI, porta host `127.0.0.1:9001` — é o alvo do túnel. |
| `worker` | Executa o grafo LangGraph a partir da fila no banco. |
| `retention-worker` | Aplica a política de retenção (LGPD). |
| `backup` | Dump diário do Postgres às 03:12, com rotação. |
| `nginx` | Reverse proxy + TLS, profile opcional `tls`; não sobe por padrão no piloto. |
| `prometheus`, `alertmanager`, `grafana` | Métricas e alertas. |
| `postgres-exporter`, `redis-exporter`, `node-exporter`, `blackbox-exporter` | Alimentam as regras de alerta. |
| `pgadmin`, `redis-commander` | Profile `debug`, não sobem por padrão. |

### Rotacionar o admin bootstrap (obrigatório antes do lançamento)

A migração cria `admin@medsafe.local` usando exclusivamente o valor aleatório de
`ADMIN_INITIAL_PASSWORD`; não há senha padrão. Faça login uma vez e troque-a pela API
autenticada. A troca invalida as sessões de refresh e o token corrente:

```bash
TOKEN=$(curl -fsS -X POST http://localhost:9001/api/v2/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@medsafe.local","password":"<ADMIN_INITIAL_PASSWORD>"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -fsS -X POST http://localhost:9001/api/v2/auth/change-password \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"current_password":"<ADMIN_INITIAL_PASSWORD>","new_password":"<NOVA_SENHA_FORTE>"}'
```

Depois de confirmar o novo login, apague o valor de `ADMIN_INITIAL_PASSWORD` do
`.env`. Migrações já aplicadas não o reutilizam. Crie usuários clínicos com o endpoint
admin `POST /api/v2/auth/register`, enviando `role` como `physician`, `pharmacist` ou
`readonly`; `pharmacist`, `physician` e `admin` podem revisar HITL.

---

## 4. Cloudflare Tunnel

O backend escuta em `127.0.0.1:9001` no host.

### Named tunnel (o único aceitável em produção)

```bash
cloudflared tunnel login
cloudflared tunnel create medsafe-api
cloudflared tunnel route dns medsafe-api api.seudominio.com
```

Crie `~/.cloudflared/config.yml`:

```yaml
tunnel: medsafe-api
credentials-file: /home/<user>/.cloudflared/<TUNNEL-UUID>.json
ingress:
  - hostname: api.seudominio.com
    service: http://localhost:9001
  - service: http_status:404
```

Rode como serviço para sobreviver a reboot:

```bash
sudo cloudflared service install
sudo systemctl status cloudflared
```

### Quick tunnel (só para teste local)

```bash
cloudflared tunnel --url http://localhost:9001
```

A URL `https://<aleatório>.trycloudflare.com` **muda a cada restart**. Não use em
produção: quando ela morre, o frontend no Vercel continua apontando para um destino
morto e todo `/api/*` passa a dar erro sem nenhum sinal no backend.

### Sempre que o hostname mudar

1. Atualize os dois rewrites em `frontend/vercel.json` (`/api/:path*` **e** `/healthz`).
   Mantenha o prefixo `/api/` no destino — sem ele o roteamento quebra inteiro.
2. Acrescente o hostname a `ALLOWED_HOSTS` no `.env` e recrie a `api`:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate api
   ```
3. Redeploy do frontend (seção 5).

---

## 5. Deploy do frontend (Vercel)

```bash
cd frontend
vercel --prod
```

A resolução da URL da API vive **em `frontend/index.html`** (bloco `API_URL`, ~linha
1168): `localhost` → `http://localhost:9001`; qualquer outro host → string vazia, ou
seja, mesma origem, dependendo do rewrite do `vercel.json`.

> `frontend/js/app.js` e `frontend/js/medsafe-api.js` têm uma implementação paralela da
> mesma lógica, mas **o `index.html` não carrega nenhum dos dois**. Editar esses
> arquivos não tem efeito — o runbook anterior mandava editá-los, e não funcionava.

---

## 6. Logs e diagnóstico

```bash
docker compose -f docker-compose.prod.yml logs -f api worker
docker compose -f docker-compose.prod.yml logs --tail=200 db
docker compose -f docker-compose.prod.yml ps

curl -fsS http://localhost:9001/healthz | python3 -m json.tool
curl -fsS http://localhost:9001/readyz
```

Como ler o `/healthz`:

| `status` | HTTP | Significado | Ação |
|---|---|---|---|
| `healthy` | 200 | Postgres, Redis e Ollama no ar | — |
| `degraded` | 200 | Ollama fora; API aceita e enfileira, mas **nenhuma análise conclui** | Suba o Ollama (seção 2) |
| `unhealthy` | 503 | Postgres ou Redis fora | Veja os logs de `db`/`redis` |

`/readyz` cobre só as dependências duras (Postgres + Redis) e devolve **503** de
verdade quando alguma está fora — use-o para gating de tráfego, não o `/healthz`.

Se `api` ou `worker` não sobem, olhe `db` e `redis` primeiro (ambos são
`condition: service_healthy`).

---

## 7. Observabilidade e alertas

Os serviços de observabilidade fazem parte do Compose de produção. A ausência das
credenciais de métricas ou Alertmanager bloqueia o preflight antes que o Compose falhe
mais tarde com uma implantação parcial.

```bash
# Prometheus (alvos e regras)
xdg-open http://127.0.0.1:9091/targets
xdg-open http://127.0.0.1:9091/alerts
# Alertmanager
xdg-open http://127.0.0.1:9093
# Grafana
xdg-open http://127.0.0.1:3001
```

O `/metrics` da API exige o Bearer token em produção. O Prometheus o lê pelo Docker
secret automaticamente. Para diagnóstico local:

```bash
METRICS_TOKEN=$(tr -d '\r\n' < secrets/prometheus/metrics_auth_token)
curl -fsS -H "Authorization: Bearer $METRICS_TOKEN" \
  http://127.0.0.1:9001/metrics | head
```

### Entrega de alertas — Discord (obrigatório ANTES de subir o stack)

Os receivers de `infra/prometheus/alertmanager.yml` entregam via webhook do Discord,
lido de `webhook_url_file: /etc/alertmanager/secrets/discord_webhook_url` — montado
do host a partir de `./secrets/alertmanager/discord_webhook_url`. Esse arquivo é
credencial: **nunca vai ao git** (`secrets/alertmanager/.gitignore` ignora tudo
exceto a si mesmo) e você o cria à mão, uma vez por máquina:

1. No Discord: **Configurações do servidor → Integrações → Webhooks → Novo webhook**,
   escolha o canal de alertas e copie a URL do webhook.
2. Grave a URL no arquivo (sem quebra de linha, permissão restrita):

```bash
mkdir -p secrets/alertmanager
printf '%s' 'https://discord.com/api/webhooks/SEU/TOKEN' > secrets/alertmanager/discord_webhook_url
chmod 600 secrets/alertmanager/discord_webhook_url
# se o stack já estava de pé:
docker compose -f docker-compose.prod.yml restart alertmanager
```

**O stack NÃO deve subir sem esse arquivo.** Detalhe de comportamento: o Alertmanager
só lê o `webhook_url_file` na hora de notificar (v0.33.1 `notify/discord/discord.go:144`),
então sem o arquivo o processo sobe e a UI funciona — mas nenhum alerta é entregue.
Por isso o healthcheck do container faz `test -s` no arquivo: secret ausente ou vazio
= container **unhealthy** em `docker compose ps`. Se o arquivo faltar no primeiro
`up`, o Docker ainda cria um *diretório* no lugar do bind-mount — apague-o
(`rm -rf secrets/alertmanager/discord_webhook_url`) antes de criar o arquivo correto.

Rotas: `severity=critical` repete a cada 30m; o resto a cada 4h — ambos no mesmo
webhook (receivers `default` e `critical`). Teste a entrega de ponta a ponta:

```bash
curl -s -X POST http://127.0.0.1:9093/api/v2/alerts -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"TesteEntrega","severity":"warning"},"annotations":{"summary":"teste","description":"entrega ok"}}]'
# a mensagem deve aparecer no canal do Discord em ~30s (group_wait)
```

**Error tracking**: `SENTRY_DSN` vazio = desligado silenciosamente. Suba o GlitchTip
(`docker-compose.glitchtip.yml`), crie o projeto, cole o DSN no `.env` e recrie
`api`/`worker`. Confirme a linha `Error tracking inicializado` no log de startup.

---

## 8. Backup e restore

O serviço `backup` faz dump diário às 03:12 em `./backups/`, formato custom (`-Fc`),
com rotação de 14 dias / 8 semanas / 6 meses.

> **Armadilha de nome de arquivo:** a imagem sempre grava com extensão `.sql.gz`, mas
> com `-Fc` o conteúdo é um **archive custom do pg_dump**, não um SQL gzipado. `gunzip`
> nesses arquivos falha com `not in gzip format`. Confirme com:
> ```bash
> head -c 5 backups/last/medsafe-latest.sql.gz   # deve imprimir: PGDMP
> docker compose -f docker-compose.prod.yml exec -T backup \
>   pg_restore -l /backups/last/medsafe-latest.sql.gz | head
> ```
> Restaure **sempre com `pg_restore` direto no arquivo**, sem `gunzip`.

> **Isto é backup local, no mesmo disco do banco.** Serve contra erro humano e
> corrupção lógica, **não** contra perda do disco ou da máquina. Copie
> `./backups/` para outro host antes de tratar dado de paciente real.

### Backup sob demanda

```bash
docker compose -f docker-compose.prod.yml exec backup /backup.sh
ls -lh backups/daily/ | tail -5
```

### Restore drill (faça antes do lançamento e a cada trimestre)

Restaure em um banco **descartável**, nunca por cima do de produção:

O `pg_restore` roda **dentro do container `backup`**, que enxerga tanto `/backups`
quanto o serviço `db` pela rede — assim não é preciso ter cliente Postgres no host nem
copiar 1 GB para dentro do container do banco.

```bash
set -a; source .env; set +a

# 1. banco de teste descartável
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "$POSTGRES_USER" -d postgres -c 'DROP DATABASE IF EXISTS restore_drill;'
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "$POSTGRES_USER" -d postgres -c 'CREATE DATABASE restore_drill;'

# 2. restaura (sem gunzip — o arquivo é archive custom, ver aviso acima).
#    A extensão pgvector precisa existir antes: o dump referencia o tipo `vector`.
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "$POSTGRES_USER" -d restore_drill -c 'CREATE EXTENSION IF NOT EXISTS vector;'
docker compose -f docker-compose.prod.yml exec -T backup \
  pg_restore -h db -U "$POSTGRES_USER" -d restore_drill \
  --no-owner --no-privileges --clean --if-exists \
  /backups/last/medsafe-latest.sql.gz

# 3. confere que veio dado de verdade (não só schema vazio)
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "$POSTGRES_USER" -d restore_drill -c \
  "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE n_live_tup > 0 ORDER BY n_live_tup DESC LIMIT 10;"

# 4. limpa
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "$POSTGRES_USER" -d postgres -c 'DROP DATABASE restore_drill;'
```

Anote data e resultado aqui:

| Data | Dump usado | Resultado |
|---|---|---|
| 2026-07-25 | primeiro dump gerado pelo serviço `backup` | ver seção "Histórico" no fim |

### Restore em produção (emergência)

`--clean --if-exists` derruba os objetos antes de recriar. Só rode com o serviço parado
e sabendo que vai sobrescrever:

```bash
docker compose -f docker-compose.prod.yml stop api worker retention-worker
docker compose -f docker-compose.prod.yml exec -T backup \
  pg_restore -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --no-owner --no-privileges --clean --if-exists \
  /backups/daily/<arquivo>.sql.gz
docker compose -f docker-compose.prod.yml start api worker retention-worker
```

> `scripts/db-backup.sh` e `infra/scripts/backup.sh` são caminhos antigos e divergentes
> (formato SQL puro, portas erradas, `/backups` hardcoded). O caminho canônico é o
> serviço `backup` + `pg_restore` acima.

---

## 9. Gate clínico (obrigatório antes de subir mudança de modelo ou prompt)

```bash
set -a; source .env; set +a
export OLLAMA_HOST=http://localhost:11434 POSTGRES_HOST=localhost POSTGRES_PORT=5433
python evals/run_eval.py
```

Só suba se `GATE OK`: `safety_critical_recall` igual ou melhor que o baseline **e**
`false_alarm_rate` igual ou melhor. Critérios e histórico em `evals/README.md`.

Último gate verde: `evals/results/20260725T172107Z_medgemma_latest.json` — commit
`594d020`, 17/17 casos, recall 1.0, falso alarme 0.0.

---

## 10. Checklist pós-deploy

```bash
# 1. containers saudáveis
docker compose -f docker-compose.prod.yml ps

# 2. saúde local e pública
curl -fsS http://localhost:9001/healthz | python3 -m json.tool
curl -fsS https://api.seudominio.com/healthz | python3 -m json.tool

# 3. análise anônima BLOQUEADA (espere 401/403)
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.seudominio.com/api/v2/analyze \
  -H 'Content-Type: application/json' -d '{"medication":"dipirona","patient_data":{}}'

# 4. docs interativos NÃO expostos (espere 404)
curl -s -o /dev/null -w '%{http_code}\n' https://api.seudominio.com/docs

# 5. fluxo real ponta a ponta (assíncrono: analyze devolve job, status consulta)
TOKEN=$(curl -fsS -X POST https://api.seudominio.com/api/v2/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@medsafe.local","password":"<sua-senha>"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

SESSION=$(curl -fsS -X POST https://api.seudominio.com/api/v2/analyze \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"medication":"sinvastatina","patient_data":{"age":60,"weight":70}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')

curl -fsS -H "Authorization: Bearer $TOKEN" \
  "https://api.seudominio.com/api/v2/status/$SESSION" | python3 -m json.tool

# 6. logs sem erro nos últimos minutos
docker compose -f docker-compose.prod.yml logs --since 5m api worker | grep -iE 'error|traceback' | head
```

O mesmo conjunto de verificações roda no CI em `.github/workflows/deploy.yml`
(`workflow_dispatch` + diário), contra a variável de repositório `MEDSAFE_PUBLIC_URL`.

---

## 11. Rollback

### Backend

```bash
git log --oneline -5
git revert <sha-ruim>
docker compose -f docker-compose.prod.yml up -d --build api worker
```

O worker trata SIGTERM: ele termina a análise em voo antes de sair (até 300s), e o que
não couber volta para `pending` em vez de ficar preso em `running`. O
`stop_grace_period` é 360s — não reduza abaixo de ~330s sem baixar também
`MEDSAFE_WORKER_DRAIN_TIMEOUT`.

### Frontend

```bash
cd frontend
vercel rollback     # sem argumento, volta ao deployment anterior
```

---

## Histórico de drills e incidentes

| Data | Evento | Resultado |
|---|---|---|
| 2026-07-25 | Auditoria de produção (config, entrega, day-2 ops) | 21 achados; blockers corrigidos neste ciclo |
| 2026-07-25 | Ollama encontrado fora do ar com `/healthz` verde | Probes corrigidos; alerta `OllamaDown` adicionado |

## Upstream stale após recreate da api (edge case E2) — RESOLVIDO 2026-08-06

**Histórico:** o nginx usava um bloco `upstream` estático, que resolve o
hostname `api` uma única vez no boot. Recriar a api sozinha (`docker compose
up -d api` após rebuild) podia dar IP novo e o nginx respondia **502** até um
restart manual.

**Fix durável (infra/nginx/nginx.conf):** `resolver 127.0.0.11 valid=10s` +
`proxy_pass` com variável (`set $medsafe_api api:9000`). O nginx re-resolve o
DNS a cada 10s e acompanha recreates automaticamente — **nenhum passo manual
é necessário**. Validado em 2026-08-06 forçando recreate da api com IP novo
(172.22.0.4 → 172.22.0.15): nginx respondeu 200 sem reload.

Se ainda ocorrer 502 após recreate (regressão), mitigação imediata:

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

Verificação: `curl -sk https://localhost/api/v2/health` deve voltar 200 com
`"status": "healthy"`.
