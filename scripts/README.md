# MedSafe Scripts

Scripts utilitários para desenvolvimento, deploy e manutenção do MedSafe.

**SKILL:** @deployment-pipeline-design - Padronização de scripts operacionais

---

## 📦 Scripts de Docker (Principais)

### Uso Diário

#### `medsafe-full-start.sh` (RECOMENDADO)
Script unificado que inicia **tudo**: Core + Monitoring + Indexes.

```bash
# Start completo (recomendado)
./scripts/medsafe-full-start.sh

# Sem stack de monitoring
./scripts/medsafe-full-start.sh --no-monitoring

# Sem aplicar indexes
./scripts/medsafe-full-start.sh --no-indexes

# Forçar rebuild das imagens
./scripts/medsafe-full-start.sh --rebuild

# Ver opções
./scripts/medsafe-full-start.sh --help
```

**O que faz:**
- ✅ Verifica dependências (Docker, Docker Compose)
- ✅ Configura ambiente (.env, diretórios)
- ✅ Inicia PostgreSQL + Ollama + API
- ✅ Aplica indexes de performance no banco
- ✅ Inicia Prometheus + Grafana (monitoring)
- ✅ Baixa modelos do Ollama configurados no .env
- ✅ Exibe URLs e status final

**Portas:**
- API/Web: http://localhost:9001
- API Docs: http://localhost:9001/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/medsafe2025)

---

#### `medsafe-full-stop.sh`
Para **todos** os serviços (Core + Monitoring).

```bash
# Parar tudo
./scripts/medsafe-full-stop.sh

# Parar e remover volumes (limpa dados)
./scripts/medsafe-full-stop.sh --clean
```

---

#### `docker-start.sh`
Inicia todos os serviços do MedSafe (PostgreSQL, Ollama, API).

```bash
./scripts/docker-start.sh
```

**O que faz:**
- ✅ Inicia PostgreSQL com pgvector
- ✅ Inicia Ollama e baixa modelos (qwen2.5:7b, qwen2.5vl:7b)
- ✅ Inicia API FastAPI
- ✅ Verifica health checks
- ✅ Exibe URLs de acesso

**Portas:**
- Frontend: http://localhost:9000
- API Docs: http://localhost:9000/docs
- Ollama: http://localhost:11434

---

#### `docker-stop.sh`
Para todos os serviços do MedSafe.

```bash
./scripts/docker-stop.sh
```

**O que faz:**
- 🛑 Para todos os containers
- 🧹 Remove volumes temporários (opcional)
- ✅ Confirma que serviços pararam

---

#### `docker-status.sh`
Verifica status de todos os serviços.

```bash
./scripts/docker-status.sh
```

**Output:**
```
✅ PostgreSQL: Running (healthy)
✅ Ollama: Running
✅ API: Running on port 9000
📊 Database: 1,234 triages, 567 reports
💾 Memory: 2.3GB used
```

---

#### `docker-logs.sh`
Visualiza logs em tempo real.

```bash
# Ver todos os logs
./scripts/docker-logs.sh

# Ver logs de um serviço específico
./scripts/docker-logs.sh api
./scripts/docker-logs.sh db
./scripts/docker-logs.sh ollama
```

**Opções:**
- `--follow` ou `-f`: Seguir logs (tail -f)
- `--lines N`: Mostrar últimas N linhas

---

## 🔧 Scripts de Manutenção

### `docker-troubleshoot.sh`
Diagnóstico automático de problemas comuns.

```bash
./scripts/docker-troubleshoot.sh
```

**Verifica:**
- ✅ Containers em execução
- ✅ Conflitos de porta
- ✅ Conectividade de rede
- ✅ Saúde do banco de dados
- ✅ Status do Ollama

**Auto-fix:** Tenta corrigir problemas automaticamente

---

### `docker-fix-network.sh`
Corrige problemas de rede do Docker.

```bash
./scripts/docker-fix-network.sh
```

**Resolve:**
- 🔧 Conflitos de subnet
- 🔧 Networks órfãs
- 🔧 DNS issues

**⚠️ Atenção:** Para todos os containers antes de executar

---

### `docker-clean-networks.sh`
Limpa networks não utilizadas.

```bash
./scripts/docker-clean-networks.sh
```

**Remove:**
- 🧹 Networks sem containers
- 🧹 Networks órfãs (dangling)
- 🧹 Cache de network

**Seguro:** Não remove networks em uso

---

## 🗄️ Scripts de Database

### `apply-db-indexes.sh`
Aplica indexes de performance no banco.

```bash
# Development
./scripts/apply-db-indexes.sh

# Production
./scripts/apply-db-indexes.sh prod
```

**Cria:**
- 29 indexes otimizados
- HNSW index para pgvector
- Full-text search indexes

**Melhoria esperada:** 30-50% em queries

**Migration:** `backend/app/db/migrations/001_add_performance_indexes.sql`

---

### `run_migrations.py`
Executa migrations do Alembic.

```bash
# Upgrade para latest
python scripts/run_migrations.py upgrade

# Downgrade 1 versão
python scripts/run_migrations.py downgrade -1

# Ver histórico
python scripts/run_migrations.py history

# Criar nova migration
alembic revision --autogenerate -m "description"
```

---

## 📊 Scripts de Dados

### `ingest_medical_data.py`
Importa dados médicos (bulas, interações, guidelines).

```bash
# Ingerir de todas as fontes
python scripts/ingest_medical_data.py --all

# Fonte específica
python scripts/ingest_medical_data.py --source FDA
python scripts/ingest_medical_data.py --source ANVISA
python scripts/ingest_medical_data.py --source DrugBank

# Com embeddings
python scripts/ingest_medical_data.py --all --embeddings
```

**Fontes suportadas:**
- FDA DailyMed API
- ANVISA Bulas
- DrugBank Interactions
- PubMed Abstracts

---

### `test_vector_search.py`
Testa busca semântica com pgvector.

```bash
# Teste básico
python scripts/test_vector_search.py

# Query customizada
python scripts/test_vector_search.py --query "interações aspirina warfarina"

# Benchmark
python scripts/test_vector_search.py --benchmark
```

---

## 🔐 Scripts de Segurança

### `security_check.py`
Auditoria de segurança completa.

```bash
# Scan completo
python scripts/security_check.py

# Scan específico
python scripts/security_check.py --secrets      # Buscar secrets expostos
python scripts/security_check.py --dependencies # Vulnerabilidades em deps
python scripts/security_check.py --code         # Análise estática (bandit)
```

**Verifica:**
- 🔒 Secrets em código
- 🔒 Vulnerabilidades conhecidas (CVE)
- 🔒 Permissões de arquivo
- 🔒 SQL injection risks

---

## 📋 Workflow Recomendado

### Desenvolvimento Diário

```bash
# 1. Iniciar ambiente
./scripts/docker-start.sh

# 2. Ver logs (em outro terminal)
./scripts/docker-logs.sh --follow

# 3. Verificar status periodicamente
./scripts/docker-status.sh

# 4. Ao finalizar
./scripts/docker-stop.sh
```

---

### Após Pull do Git

```bash
# 1. Atualizar containers
./scripts/docker-start.sh

# 2. Rodar migrations
python scripts/run_migrations.py upgrade

# 3. Aplicar indexes (se houver novos)
./scripts/apply-db-indexes.sh

# 4. Verificar health
./scripts/docker-status.sh
```

---

### Troubleshooting

```bash
# 1. Diagnóstico automático
./scripts/docker-troubleshoot.sh

# 2. Se houver problemas de rede
./scripts/docker-fix-network.sh

# 3. Limpar e reiniciar
./scripts/docker-stop.sh
./scripts/docker-clean-networks.sh
./scripts/docker-start.sh
```

---

### Deploy para Produção

```bash
# 1. Backup do banco
# (usar infra/scripts/backup.sh)

# 2. Aplicar migrations
python scripts/run_migrations.py upgrade

# 3. Aplicar indexes
./scripts/apply-db-indexes.sh prod

# 4. Verificar security
python scripts/security_check.py

# 5. Iniciar serviços
./scripts/docker-start.sh
```

---

## 🚨 Scripts Removidos (Deprecados)

Os seguintes scripts foram removidos por serem duplicados ou obsoletos:

- ❌ `start.sh` → Use `docker-start.sh`
- ❌ `stop.sh` → Use `docker-stop.sh`
- ❌ `status.sh` → Use `docker-status.sh`
- ❌ `start_hf.sh` → Específico HuggingFace (não usado)
- ❌ `test_real_analysis.sh` → Use `pytest backend/tests/`

---

## 📚 Referências

- [Docker Compose Documentation](../docker-compose.yml)
- [Alembic Migrations](../alembic/)
- [Database Schema](../backend/app/db/models.py)
- [API Documentation](http://localhost:9000/docs)

---

**Última atualização:** 01/12/2025
**Mantido por:** Equipe MedSafe
