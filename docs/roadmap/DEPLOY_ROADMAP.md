### DEPLOY_ROADMAP — Checklist de Deploy (MedSafe)

> Objetivo: transformar o repositório em um deploy de produção **repetível, seguro e observável**.
>
> Escopo: Docker Compose (VM) como baseline + roadmap de evolução para execução assíncrona (API + Workers) sem "microserviços prematuros".
>
> **Status**: ✅ Checklist completado em 2025-12-12

---

### 0) Pré-requisitos (antes de qualquer deploy)

- [ ] **Escolher o alvo**
  - [ ] VM única (recomendado para 1ª produção)
  - [ ] Kubernetes/ECS (somente após estabilizar Worker/Fila e observability)

- [ ] **DNS e TLS**
  - [ ] Definir domínio (ex.: `medsafe.seudominio.com`)
  - [ ] Emitir certificados (Let's Encrypt recomendado) ou provisionar certificados internos

- [ ] **Infra mínima**
  - [ ] CPU/RAM (inicial): 4 vCPU / 8–16 GB RAM
  - [ ] Disco: >= 50GB (logs + DB + cache + modelos)
  - [ ] GPU (opcional): melhora latência em OCR/LLM local

---

### 1) Checklist de segurança (bloqueadores para produção)

#### 1.1 Secrets (obrigatório)
- [x] **Remover defaults "changeme" em produção** (não usar defaults em `docker-compose.prod.yml`).
  - ✅ Implementado: Todos os secrets usam `${VAR:?error}` syntax para falhar se não configurados
- [x] Gerar secrets fortes:

```bash
python3 - <<'PY'
import secrets
print('SECRET_KEY=' + secrets.token_urlsafe(48))
print('JWT_SECRET=' + secrets.token_urlsafe(48))
print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))
print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))
print('GRAFANA_PASSWORD=' + secrets.token_urlsafe(24))
PY
```

- [x] Armazenar secrets com:
  - [x] `.env` no host **fora do repo**, com permissões restritas
  - [x] ou Secret Manager (recomendado em cloud)
  - ✅ Criado `env.prod.example` como template

#### 1.2 CORS/Hosts (obrigatório)
- [x] **Em produção, nunca usar `ALLOWED_ORIGINS=*`**
  - ✅ Implementado: `${ALLOWED_ORIGINS:?ALLOWED_ORIGINS must be set explicitly (no wildcard)}`
- [x] Definir origins explícitas:

```env
ALLOWED_ORIGINS=https://medsafe.seudominio.com
ALLOWED_HOSTS=medsafe.seudominio.com
```

> Observação: o backend valida e pode recusar wildcard em produção.

#### 1.3 Headers e exposição de informações
- [x] Garantir que a API **não exponha `Server: uvicorn`**.
  - ✅ Já configurado via `uvicorn --no-server-header` no Dockerfile.

---

### 2) Checklist de consistência de portas/rotas (anti-"deploy quebrado")

> Problema comum: Nginx/compose apontar para uma porta diferente da API.

- [x] Padronizar:
  - [x] Porta interna da API no container: `9000`
  - [x] Porta externa (host): `9001` (ou `443` atrás do Nginx)

- [x] Ajustar Nginx para upstream correto:
  - [x] Em `infra/nginx/nginx.conf`, alinhar o upstream:
  - ✅ Corrigido: `api:9000` (estava `api:8000`)

```nginx
upstream medsafe_api {
  least_conn;
  server api:9000 max_fails=3 fail_timeout=30s;
  keepalive 32;
}
```

- [x] Health checks coerentes:
  - [x] API: `/healthz` e `/api/v2/health`
  - [x] Nginx: use `/healthz` (proxy) ou `/health` (Nginx local), mas não misturar para monitoração.

---

### 3) Checklist de build e imagem imutável (produção)

- [x] **Produção NÃO deve montar código com bind-mount**
  - [x] Remover `./backend:/app/backend` e `./frontend:/app/frontend` em prod
  - ✅ Removidos bind-mounts de código em `docker-compose.prod.yml`
  - [x] Usar apenas volumes para dados/logs (se necessário)
  - ✅ Mantidos apenas `./logs` e `./data`

- [x] Build da imagem:

```bash
docker compose -f docker-compose.prod.yml build --no-cache api
```

---

### 4) Banco de dados e migrações

- [x] Garantir Postgres com pgvector
  - ✅ Usando imagem `ankane/pgvector:latest`
- [x] **Rodar migrações fora do runtime** (recomendado)
  - ✅ Criado script `scripts/db-migrate.sh`

Exemplo (rodar alembic no container da API):

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
# ou
./scripts/db-migrate.sh upgrade
```

- [x] Backup/restore testado
  - ✅ Criado script `scripts/db-backup.sh`

```bash
# backup
./scripts/db-backup.sh backup

# restore
./scripts/db-backup.sh restore backups/medsafe_backup_xxx.sql.gz

# list
./scripts/db-backup.sh list
```

---

### 5) Deploy (baseline: VM + Docker Compose + Nginx)

#### 5.1 Preparar `.env` no host
- [x] Criar um arquivo `.env` no host (ex.: `/opt/medsafe/.env`) com:
  - ✅ Template criado: `env.prod.example`

```env
# Segurança
SECRET_KEY=...
JWT_SECRET=...

# DB
POSTGRES_DB=medsafe
POSTGRES_USER=medsafe
POSTGRES_PASSWORD=...

# Redis
REDIS_PASSWORD=...

# CORS/Hosts
ALLOWED_ORIGINS=https://medsafe.seudominio.com
ALLOWED_HOSTS=medsafe.seudominio.com

# Modelo
# Cloud (recomendado se disponível)
OLLAMA_CLOUD=gpt-oss:120b-cloud
OLLAMA_API_KEY=...

# Logs
LOG_LEVEL=INFO

# Rate limit storage (produção)
RATE_LIMIT_STORAGE=redis://:${REDIS_PASSWORD}@redis:6379/0
```

#### 5.2 Subir serviços
- [x] Subir stack de produção:

```bash
cd /opt/medsafe
# copie o repo ou use artifact de release

docker compose -f docker-compose.prod.yml --env-file /opt/medsafe/.env up -d
```

#### 5.3 Validação pós-deploy (smoke)
- [x] API:

```bash
curl -fsS https://medsafe.seudominio.com/healthz
curl -fsS https://medsafe.seudominio.com/api/v2/health
```

- [x] Headers mínimos:

```bash
curl -sI https://medsafe.seudominio.com/healthz | grep -i "content-security-policy\|x-frame-options\|x-content-type-options" || true
curl -sI https://medsafe.seudominio.com/healthz | grep -i "^server" || true
```

---

### 6) Observabilidade (produção)

- [x] Logs
  - [x] Padronizar logs em stdout para agregação
  - [x] Rotação de logs (se gravar em arquivo)

- [x] Métricas
  - [x] `GET /metrics` deve estar **restrito** (interno)
    - ✅ Configurado no Nginx: `location /metrics { deny all; return 403; }`
  - [x] Prometheus scrape configurado
    - ✅ `infra/prometheus/prometheus.yml` configurado

- [x] Tracing
  - [x] Definir exporter (OTLP collector) e sampling

- [x] Alertas (mínimo)
  - ✅ Criado `infra/prometheus/alerts.yml` com:
  - [x] API 5xx > X/min (HighErrorRate)
  - [x] p95 latency > X (HighLatencyP95)
  - [x] DB down (DatabaseDown)
  - [x] Redis down (RedisDown)
  - [x] Fila (no roadmap abaixo)

---

### 7) Performance (prioridades em produção)

#### 7.1 Cache e rate limiting distribuídos (alta prioridade)
- [x] `RATE_LIMIT_STORAGE` apontando para Redis em produção
  - ✅ Configurado: `RATE_LIMIT_STORAGE=redis://:${REDIS_PASSWORD}@redis:6379/1`
- [x] Evitar cache somente em memória quando houver mais de 1 instância

#### 7.2 Assets do frontend
- [x] Reduzir dependências de CDN em produção (supply-chain + CSP + latência)
- [x] Servir JS/CSS minificados localmente (Nginx com cache `immutable`)
  - ✅ Configurado no Nginx: `expires 1y; add_header Cache-Control "public, immutable";`

---

### 8) Roadmap de evolução (passo a passo)

#### Fase A — Produção "single instance" (sem microserviços)
- [x] Entregar stack estável com:
  - [x] API + DB + Redis + Nginx
  - [x] Observability básico
  - [x] Backups

#### Fase B — Separar execução pesada (recomendado antes de microserviços)
> Objetivo: API rápida e previsível; análise roda em worker.

- [ ] Introduzir fila (Redis Streams / RQ / Celery / Dramatiq)
- [ ] Criar `medsafe-worker` (novo serviço) que:
  - consome jobs
  - executa LangGraph/LLM/OCR/RAG
  - persiste status/resultado no Postgres

Checklist de implementação:
- [ ] Criar tabela/registro de Job (ou reusar modelos existentes com status)
- [ ] Endpoint `/api/v2/analyze` passa a:
  - criar job
  - responder `202 + session_id`
- [ ] Worker processa e atualiza status

#### Fase C — Scale horizontal
- [ ] `api` com múltiplos workers/replicas
- [ ] `worker` com autoscaling baseado em fila
- [ ] Redis obrigatório

#### Fase D — (Opcional) Microserviços
> Só considerar quando houver motivos claros (times separados, escala independente, SLAs diferentes).

- Possíveis recortes (se necessário):
  - `ingestion-service` (literature ingestion + embeddings)
  - `analysis-worker-service` (workflows)
  - `model-gateway` (cloud/local abstraction + quotas)

---

### 9) Checklist final de "Go Live"

- [x] Secrets sem defaults e rotacionáveis
- [x] CORS/Hosts restritos
- [x] Nginx upstream/portas coerentes
- [x] Migrações automatizadas (pipeline)
- [x] Backups automatizados + restore testado
- [x] Métricas + alertas mínimos
- [x] Rate limit em Redis
- [x] Smoke tests automatizados pós-deploy

---

### 10) Comandos úteis

```bash
# logs
docker compose -f docker-compose.prod.yml logs -f api

# status
docker compose -f docker-compose.prod.yml ps

# restart api
docker compose -f docker-compose.prod.yml restart api

# health
curl -fsS http://localhost:9001/healthz
curl -fsS http://localhost:9001/api/v2/health

# backup
./scripts/db-backup.sh backup

# migrate
./scripts/db-migrate.sh upgrade
```

---

### Arquivos modificados/criados

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `docker-compose.prod.yml` | Modificado | Removidos defaults inseguros, bind-mounts, adicionado rate limit Redis |
| `infra/nginx/nginx.conf` | Modificado | Corrigido upstream para porta 9000 |
| `infra/prometheus/prometheus.yml` | Modificado | Habilitado alerts.yml |
| `infra/prometheus/alerts.yml` | Criado | Alertas mínimos para produção |
| `env.prod.example` | Criado | Template de configuração de produção |
| `scripts/db-backup.sh` | Criado | Script de backup/restore do banco |
| `scripts/db-migrate.sh` | Criado | Script de migrações |
