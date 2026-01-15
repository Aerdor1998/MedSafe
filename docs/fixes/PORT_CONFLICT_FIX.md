# 🔧 Correção - Conflitos de Porta Docker

## 🐛 Erros Identificados

### Erro 1: Ollama - Porta 11434
```
Error response from daemon: driver failed programming external connectivity on endpoint medsafe_ollama:
failed to bind port 0.0.0.0:11434/tcp: Error starting userland proxy:
listen tcp4 0.0.0.0:11434: bind: address already in use
```

**Causa:** Container Ollama existente (ID: 78d5a93960ce) já usando porta 11434

---

### Erro 2: PostgreSQL - Porta 5432
```
Error response from daemon: driver failed programming external connectivity on endpoint medsafe_db:
Bind for 0.0.0.0:5432 failed: port is already allocated
```

**Causa:** Container medsafe-postgres (ID: 0b00f8439fdd) já usando porta 5432

---

### Erro 3: API - Porta 9000
```
Error response from daemon: driver failed programming external connectivity on endpoint medsafe_api:
failed to bind port 0.0.0.0:9000/tcp: Error starting userland proxy:
listen tcp4 0.0.0.0:9000: bind: address already in use
```

**Causa:** Processos Python (PIDs: 260164, 260168) já usando porta 9000

---

### Erro 4: Ollama Command
```
Error: unknown command "sh" for "ollama"
Did you mean this?
	show
	push
	ps
```

**Causa:** Entrypoint do Ollama é `/bin/ollama`, não aceita `sh -c`

---

## 🛠️ SKILLS UTILIZADAS

### 1. **debugging-strategies** 🔍

**Onde aplicado:**
- Diagnóstico de conflitos de porta (todos os 3 conflitos)
- Análise de logs do container Ollama
- Identificação de processos conflitantes

**Por quê:**
- Identificar quais processos/containers estão usando as portas
- Mapear todas as portas em uso no sistema
- Prevenir conflitos futuros

**O que foi feito:**

#### A) Diagnóstico de Portas
```bash
# SKILL: debugging-strategies
# Identificar processos usando portas

# Porta 11434 (Ollama)
lsof -i :11434
# Encontrou: Container ollama (78d5a93960ce)

# Porta 5432 (PostgreSQL)
docker ps | grep postgres
# Encontrou: Container medsafe-postgres (0b00f8439fdd)

# Porta 9000 (API)
lsof -i :9000
# Encontrou: Processos Python (PIDs: 260164, 260168)
```

**Evidência no código:**
```yaml
# docker-compose.yml (Ollama)
# SKILL: debugging-strategies
# FIX: Port 11434 conflitava com ollama container existente (ID: 78d5a93960ce)
# Mudado para 11435 no host, mantém 11434 interno no container
ports:
  - "11435:11434"

# docker-compose.yml (PostgreSQL)
# SKILL: debugging-strategies
# FIX: Port 5432 conflitava com medsafe-postgres container existente (ID: 0b00f8439fdd)
# Mudado para 5433 no host, mantém 5432 interno no container
ports:
  - "5433:5432"

# docker-compose.yml (API)
# SKILL: debugging-strategies
# FIX: Port 9000 conflitava com processo Python existente (PIDs: 260164, 260168)
# Mudado para 9001 no host, mantém 9000 interno no container
ports:
  - "9001:9000"
```

#### B) Diagnóstico do Comando Ollama
```bash
# SKILL: debugging-strategies
# Verificar logs do container
docker logs medsafe_ollama

# Encontrado: "Error: unknown command "sh" for "ollama""
# Causa: Entrypoint é /bin/ollama, não aceita sh -c
```

**Solução:**
```yaml
# docker-compose.yml
# SKILL: debugging-strategies
# FIX: Comando 'sh -c' não funciona porque entrypoint é '/bin/ollama'
# Removido command - Ollama inicia automaticamente com 'ollama serve'
# Modelos são baixados depois via docker-start.sh (linha 278-290)
```

---

### 2. **deployment-pipeline-design** 🚀

**Onde aplicado:**
- Escolha estratégica de portas alternativas
- Mapeamento host:container para evitar mudanças internas
- Consistência entre docker-compose.yml e docker-compose.prod.yml
- Atualização de scripts de inicialização

**Por quê:**
- Garantir que aplicação funcione sem conflitos com outros serviços
- Manter consistência entre ambientes (dev = prod)
- Facilitar troubleshooting e debugging

**O que foi feito:**

#### A) Estratégia de Port Mapping
```yaml
# SKILL: deployment-pipeline-design
# Containers comunicam via rede interna Docker, então OLLAMA_HOST
# permanece http://ollama:11434 (usa porta interna do container)
#
# Apenas mapeamento externo muda:
# - Host: localhost:11435
# - Container: 11434
ports:
  - "11435:11434"
```

**Benefícios:**
- ✅ Aplicação não precisa ser alterada (usa portas internas)
- ✅ DATABASE_URL continua usando `db:5432` (rede interna)
- ✅ OLLAMA_HOST continua usando `http://ollama:11434` (rede interna)
- ✅ Apenas acesso externo (localhost) usa novas portas

#### B) Mapeamento de Portas

**Antes:**
| Serviço | Porta Host | Porta Container | Status |
|---------|------------|-----------------|--------|
| API | 9000 | 9000 | ❌ Conflito |
| PostgreSQL | 5432 | 5432 | ❌ Conflito |
| Ollama | 11434 | 11434 | ❌ Conflito |

**Depois:**
| Serviço | Porta Host | Porta Container | Status |
|---------|------------|-----------------|--------|
| API | **9001** | 9000 | ✅ OK |
| PostgreSQL | **5433** | 5432 | ✅ OK |
| Ollama | **11435** | 11434 | ✅ OK |

#### C) Atualização docker-start.sh
```bash
# docker-start.sh (linha 273)
# SKILL: debugging-strategies
# FIX: Porta mudada de 9000 para 9001 devido a conflito
wait_for_service "API" 60 "curl -f http://localhost:9001/healthz"

# docker-start.sh (linhas 304-309)
# SKILL: debugging-strategies
# FIX: Porta mudada de 9000 para 9001 devido a conflito com processo Python
echo "   🌐 Interface Web:    http://localhost:9001"
echo "   📚 API Docs:         http://localhost:9001/docs"
echo "   📖 ReDoc:            http://localhost:9001/redoc"
echo "   💚 Health Check:     http://localhost:9001/healthz"
```

#### D) Consistência Dev/Prod
```yaml
# docker-compose.prod.yml
# SKILL: deployment-pipeline-design
# Mantém consistência com docker-compose.yml (dev = prod)
ports:
  - "11435:11434"  # Ollama
  - "5433:5432"    # PostgreSQL
  - "9001:9000"    # API
```

---

## 📊 Comparação Antes vs Depois

| Aspecto | Antes | Depois | Skill |
|---------|-------|--------|-------|
| **Porta API (host)** | 9000 | 9001 | debugging-strategies |
| **Porta PostgreSQL (host)** | 5432 | 5433 | debugging-strategies |
| **Porta Ollama (host)** | 11434 | 11435 | debugging-strategies |
| **Portas internas** | Mesmas | Mesmas (9000, 5432, 11434) | deployment-pipeline-design |
| **Comando Ollama** | sh -c "..." (❌ Falha) | Removido (✅ OK) | debugging-strategies |
| **Conflitos?** | ❌ Sim (3 conflitos) | ✅ Não | debugging-strategies |
| **Containers rodando?** | ❌ Falha | ✅ Sucesso | deployment-pipeline-design |
| **Health checks** | N/A | ✅ Todos OK | deployment-pipeline-design |

---

## 🚀 Arquivos Modificados

### 1. **docker-compose.yml** ✅

**Skills:** debugging-strategies + deployment-pipeline-design

```diff
services:
  ollama:
    ports:
-     - "11434:11434"
+     - "11435:11434"
-   command: >
-     sh -c "
-       ollama serve &
-       sleep 10 &&
-       ollama pull qwen3:4b &&
-       ollama pull qwen2.5vl:7b &&
-       wait
-     "
+   # SKILL: debugging-strategies
+   # FIX: Comando 'sh -c' não funciona porque entrypoint é '/bin/ollama'
+   # Removido command - Ollama inicia automaticamente com 'ollama serve'

  db:
    ports:
-     - "5432:5432"
+     - "5433:5432"

  api:
    ports:
-     - "9000:9000"
+     - "9001:9000"
```

---

### 2. **docker-compose.prod.yml** ✅

**Skills:** deployment-pipeline-design

```diff
services:
  ollama:
    ports:
-     - "11434:11434"
+     - "11435:11434"

  db:
    ports:
-     - "5432:5432"
+     - "5433:5432"

  api:
    ports:
-     - "9000:9000"
+     - "9001:9000"
```

---

### 3. **docker-start.sh** (modificado) ✅

**Skills:** debugging-strategies

**Mudanças:**
- Linha 273: Health check da API usa porta 9001
- Linhas 304-309: URLs de acesso usam porta 9001
- Linha 328: Comando curl de teste usa porta 9001

```bash
# Linha 273
- wait_for_service "API" 60 "curl -f http://localhost:9000/healthz"
+ wait_for_service "API" 60 "curl -f http://localhost:9001/healthz"

# Linhas 304-309
- echo "   🌐 Interface Web:    http://localhost:9000"
+ echo "   🌐 Interface Web:    http://localhost:9001"
# (e todas as outras URLs)

# Linha 328
- echo "   curl http://localhost:9000/healthz | jq"
+ echo "   curl http://localhost:9001/healthz | jq"
```

---

## 🔄 Fluxo de Resolução

```
┌──────────────────────────────────────────┐
│ ERRO 1: Porta 11434 em uso (Ollama)     │
└──────────────────┬───────────────────────┘
                   │
      ┌────────────▼────────────┐
      │ 1. Diagnosticar         │
      │ lsof -i :11434          │
      │ docker ps | grep ollama │
      └────────────┬────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 2. Identificar Conflito     │
      │ Container: ollama (existente)│
      │ → CONFLITO!                 │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 3. Mudar Porta Host         │
      │ 11434 → 11435               │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 4. Testar                   │
      │ docker-compose up -d        │
      │ → ✅ Ollama OK!             │
      └────────────┬────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│ ERRO 2: Porta 5432 em uso (PostgreSQL)  │
└──────────────────┬───────────────────────┘
                   │
      ┌────────────▼────────────┐
      │ 5. Diagnosticar         │
      │ docker ps | grep postgres│
      └────────────┬────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 6. Identificar Conflito     │
      │ Container: medsafe-postgres │
      │ → CONFLITO!                 │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 7. Mudar Porta Host         │
      │ 5432 → 5433                 │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 8. Testar                   │
      │ docker-compose up -d        │
      │ → ✅ PostgreSQL OK!         │
      └────────────┬────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│ ERRO 3: Command "sh" inválido (Ollama)  │
└──────────────────┬───────────────────────┘
                   │
      ┌────────────▼────────────┐
      │ 9. Diagnosticar         │
      │ docker logs medsafe_ollama│
      └────────────┬────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 10. Identificar Problema    │
      │ Entrypoint é /bin/ollama    │
      │ → Não aceita 'sh -c'        │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 11. Remover command         │
      │ Ollama serve automático     │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 12. Testar                  │
      │ docker-compose up -d        │
      │ → ✅ Ollama iniciando!      │
      └────────────┬────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│ ERRO 4: Porta 9000 em uso (API)         │
└──────────────────┬───────────────────────┘
                   │
      ┌────────────▼────────────┐
      │ 13. Diagnosticar        │
      │ lsof -i :9000           │
      └────────────┬────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 14. Identificar Conflito    │
      │ Processos Python: 260164,   │
      │ 260168 → CONFLITO!          │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 15. Mudar Porta Host        │
      │ 9000 → 9001                 │
      │ Atualizar docker-start.sh   │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 16. Testar                  │
      │ docker-compose up -d        │
      │ → ✅ API OK!                │
      └────────────┬────────────────┘
                   │
      ┌────────────▼────────────────┐
      │ 17. Verificar Health        │
      │ curl localhost:9001/healthz │
      │ → ✅ TODOS SERVIÇOS OK!     │
      └─────────────────────────────┘
```

---

## ✅ Status Final

### Containers Rodando
```bash
$ docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
NAMES                  STATUS                             PORTS
medsafe_api            Up 11 seconds (healthy)            0.0.0.0:9001->9000/tcp
medsafe_db             Up 42 seconds (healthy)            0.0.0.0:5433->5432/tcp
medsafe_ollama         Up 42 seconds (healthy)            0.0.0.0:11435->11434/tcp
```

### Health Check
```bash
$ curl http://localhost:9001/healthz
{
  "status": "healthy",
  "timestamp": "2025-11-12T13:43:26.079031",
  "version": "1.0.0",
  "services": {
    "database": "ok",
    "ollama": "ok",
    "api": "ok"
  }
}
```

---

## 📍 URLs de Acesso (ATUALIZADAS)

### Antes (❌ Não funcionavam)
```
Interface Web:    http://localhost:9000  ← CONFLITO
API Docs:         http://localhost:9000/docs
PostgreSQL:       localhost:5432  ← CONFLITO
Ollama:           http://localhost:11434  ← CONFLITO
```

### Depois (✅ Funcionando)
```
Interface Web:    http://localhost:9001  ✅
API Docs:         http://localhost:9001/docs  ✅
ReDoc:            http://localhost:9001/redoc  ✅
Health Check:     http://localhost:9001/healthz  ✅
PostgreSQL:       localhost:5433  ✅
Ollama:           http://localhost:11435  ✅
```

**Importante:** Comunicação interna entre containers **não muda**:
```bash
# API → PostgreSQL (rede interna Docker)
DATABASE_URL=postgresql://medsafe:password@db:5432/medsafe  # Porta 5432 (interna)

# API → Ollama (rede interna Docker)
OLLAMA_HOST=http://ollama:11434  # Porta 11434 (interna)
```

---

## 🎯 Comandos Úteis (ATUALIZADOS)

### Acessar serviços
```bash
# API Health Check
curl http://localhost:9001/healthz | jq

# API Docs (Swagger)
open http://localhost:9001/docs

# PostgreSQL (via host)
psql -h localhost -p 5433 -U medsafe -d medsafe

# PostgreSQL (via Docker network)
docker exec -it medsafe_db psql -U medsafe -d medsafe

# Ollama (via host)
curl http://localhost:11435/api/tags

# Ollama (via Docker)
docker exec medsafe_ollama ollama list
```

### Verificar portas em uso
```bash
# Ver todas as portas do MedSafe
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep medsafe

# Ver processo usando porta específica
lsof -i :9001    # API
lsof -i :5433    # PostgreSQL
lsof -i :11435   # Ollama
```

### Logs
```bash
# Todos os containers
docker-compose logs -f

# Apenas API
docker-compose logs -f api

# Apenas Ollama
docker-compose logs -f ollama

# Apenas PostgreSQL
docker-compose logs -f db
```

---

## 🔍 Prevenção Futura

### 1. Verificar portas antes de subir
```bash
# Verificar se portas estão livres
lsof -i :9001  # API
lsof -i :5433  # PostgreSQL
lsof -i :11435 # Ollama

# Se retornar vazio, porta está livre
```

### 2. Documentar portas usadas
```bash
# Criar arquivo de referência
cat > /etc/docker/ports.txt <<EOF
# MedSafe (Docker)
9001 - MedSafe API (era 9000)
5433 - MedSafe PostgreSQL (era 5432)
11435 - MedSafe Ollama (era 11434)

# Outros projetos
9000 - MedSafe API (processo Python local)
5432 - medsafe-postgres (container)
11434 - ollama (container existente)
EOF
```

### 3. Parar serviços conflitantes antes
```bash
# Parar processo Python na porta 9000
lsof -ti :9000 | xargs kill -9

# Parar containers conflitantes
docker stop ollama medsafe-postgres

# OU usar portas diferentes (recomendado)
```

---

## 🆘 Se Houver Novos Conflitos

### Passo 1: Diagnosticar
```bash
# Identificar processo usando porta
lsof -i :PORTA

# Ver containers usando porta
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep PORTA
```

### Passo 2: Decidir
**Opção A:** Parar processo conflitante
```bash
# Matar processo
kill -9 PID

# Ou parar container
docker stop CONTAINER_NAME
```

**Opção B:** Mudar porta do MedSafe (recomendado)
```bash
# Editar docker-compose.yml
# Mudar de "PORTA_ANTIGA:PORTA_CONTAINER" para "NOVA_PORTA:PORTA_CONTAINER"
# Exemplo: "9002:9000" (nova porta 9002, container continua 9000)
```

### Passo 3: Atualizar scripts e docs
```bash
# Atualizar docker-start.sh
# Atualizar README
# Atualizar este documento
```

---

## 📚 Referências

### Documentação relacionada
- [NETWORK_CONFLICT_FIX.md](./NETWORK_CONFLICT_FIX.md) - Conflito de subnet Docker
- [DOCKERFILE_FIX.md](./DOCKERFILE_FIX.md) - Correção libgl1-mesa-glx
- [NETWORK_FIX_GUIDE.md](./NETWORK_FIX_GUIDE.md) - Conectividade Docker Hub

### Port mapping Docker
- Formato: `"HOST_PORT:CONTAINER_PORT"`
- Acesso externo: `localhost:HOST_PORT`
- Rede interna Docker: `service_name:CONTAINER_PORT`

### Ollama entrypoint
- Image: `ollama/ollama:latest`
- Entrypoint: `/bin/ollama`
- Comando padrão: `serve`
- **Não aceita** `sh -c` como command

---

**Versão:** 1.0.0
**Data:** 2025-11-12
**Problemas:** Conflitos de porta 9000, 5432, 11434 + comando Ollama inválido
**Soluções:** Portas 9001, 5433, 11435 + remoção de command
**Status:** ✅ RESOLVIDO - Todos os serviços rodando

---

**Skills Aplicadas:**
1. ✅ **debugging-strategies** - Diagnóstico de conflitos e análise de logs
2. ✅ **deployment-pipeline-design** - Port mapping estratégico e consistência dev/prod
