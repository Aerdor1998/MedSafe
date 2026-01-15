# Docker Cache Fix - Código Atualizado Não Aplicado

**Data:** 01/12/2025
**Issue:** Código atualizado não estava sendo executado (Docker cache)
**Skills:** @debugging-strategies, @deployment-pipeline-design

---

## 🐛 Problema Identificado

### **Código atualizado não executado** ❌

**Evidência nos logs:**
```
🚨 [2025-12-01 19:47:41.415] [ERROR] [base_agent]
   ❌ ClinicalAgent error: 'timestamps'
   File "/app/backend/app/langgraph_agents/clinical_agent.py", line 149
     updates["timestamps"]["clinical_analysis_end"] = datetime.now()
KeyError: 'timestamps'
```

**Mas o código foi corrigido:**
```python
# Linhas 146-149 (CORRIGIDAS):
if "timestamps" not in updates:
    updates["timestamps"] = state.get("timestamps", {}).copy()
updates["timestamps"]["clinical_analysis_end"] = datetime.now()
```

**Causa Raiz:**
- Docker estava usando **imagem cached antiga**
- `COPY backend/ ./backend/` no Dockerfile (linha 48) não rebuilda automaticamente
- Docker só rebuild se `requirements.txt` mudar (linha 37-45)
- **Mudanças em arquivos Python não triggam rebuild!**

---

## ✅ Solução Aplicada

### **Rebuild Forçado sem Cache**

**Comando executado:**
```bash
cd /home/lucasmsilva/Documentos/Cursor/MedSafe
docker-compose stop api
docker-compose build --no-cache api
docker-compose up -d api
```

**O que `--no-cache` faz:**
- ✅ Ignora TODAS as layers cached do Docker
- ✅ Reinstala requirements.txt (48 segundos)
- ✅ Recopia `backend/`, `frontend/`, `static/`
- ✅ Garante que código mais recente está na imagem

---

## 📊 Resultado

### **Antes do rebuild:**
```bash
$ docker exec medsafe_api cat /app/backend/app/langgraph_agents/clinical_agent.py | grep -A 3 "Update timestamps"

# Update timestamps
if "timestamps" not in state:  # ❌ ERRADO - modifica state
    updates["timestamps"] = {}
updates["timestamps"]["clinical_analysis_end"] = datetime.now()
```

### **Depois do rebuild:**
```bash
$ docker exec medsafe_api cat /app/backend/app/langgraph_agents/clinical_agent.py | grep -A 3 "Update timestamps"

# Update timestamps - ensure timestamps dict exists in updates
if "timestamps" not in updates:  # ✅ CORRETO - modifica updates
    updates["timestamps"] = state.get("timestamps", {}).copy()
updates["timestamps"]["clinical_analysis_end"] = datetime.now()
```

---

## 🔧 Plano de Ação Completo

### **Etapa 1: Diagnóstico** ✅
```bash
# Verificar código no container
docker exec medsafe_api cat /app/backend/app/langgraph_agents/clinical_agent.py | grep -n "timestamps"

# Se mostrar linha 149 antiga → Docker cache problem
```

### **Etapa 2: Parar API** ✅
```bash
docker-compose stop api
```

### **Etapa 3: Rebuild sem cache** ✅
```bash
# --no-cache: Ignora TODAS as layers cached
docker-compose build --no-cache api

# Output esperado:
# [api 7/10] COPY backend/ ./backend/  ← Recopia código
# Successfully built f80f61b62d32
```

**Duração:** ~60 segundos (reinstala requirements.txt)

### **Etapa 4: Reiniciar container** ✅
```bash
docker-compose up -d api
```

### **Etapa 5: Validar código atualizado** ✅
```bash
# Verificar ClinicalAgent
docker exec medsafe_api cat /app/backend/app/langgraph_agents/clinical_agent.py | grep -A 5 "Update timestamps"

# Deve mostrar:
# if "timestamps" not in updates:  ✅
#     updates["timestamps"] = state.get("timestamps", {}).copy()

# Verificar DrugInteractionService
docker exec medsafe_api grep -n "find_interactions" /app/backend/app/services/drug_interactions.py

# Deve mostrar:
# 293:    def find_interactions(...) ← Método atualizado
```

### **Etapa 6: Health check** ✅
```bash
curl -s http://localhost:9001/healthz | python3 -m json.tool

# Output esperado:
# {
#     "status": "healthy",
#     "version": "2.0.0-langgraph",
#     "services": {
#         "database": "ok",
#         "api": "ok"
#     }
# }
```

---

## 🧪 Como Testar Agora

### **Teste 1: Interação CRÍTICA (Fenelzina + Ritalina)**

**No frontend:**
1. Medicamento: `Fenelzina`
2. Medicamento atual: `Ritalina`
3. Condição: `Depressão`

**Resultado esperado:**
```
✅ RISCO CRÍTICO
✅ 1 interação encontrada (CRÍTICA)
✅ Fenelzina + Methylphenidate
✅ Descrição: "The risk or severity of adverse effects..."
✅ Confiança: 85-90%
```

**Logs esperados:**
```bash
docker logs medsafe_api -f | grep -E "(interações|RISCO|timestamps)"

# Deve mostrar:
# 📊 Total de interações encontradas: 1 (escaneadas X linhas)  ← RAG otimizado
# 🔴 RISCO CRÍTICO identificado
# timestamps["clinical_analysis_end"] = ...  ← Sem KeyError!
```

### **Teste 2: Verificar RAG otimizado**

**Logs devem mostrar busca sob demanda:**
```bash
docker logs medsafe_api --tail 100 | grep "interações"

# ✅ Deve mostrar:
# "Total de interações encontradas: 1 (escaneadas 191135 linhas)"
#
# ❌ NÃO deve mostrar:
# "Base carregada: 382270 interações indexadas"
```

### **Teste 3: Verificar GPU ativa**

**Durante análise:**
```bash
watch -n 1 nvidia-smi

# Deve mostrar:
# GPU Util: 80-100%
# Memory Used: ~4-5 GB (qwen3:8b carregado)
```

---

## 🐛 Troubleshooting

### **Se KeyError 'timestamps' ainda acontecer:**

```bash
# 1. Verificar se código atualizado está no container
docker exec medsafe_api cat /app/backend/app/langgraph_agents/clinical_agent.py | grep -A 3 "timestamps"

# Se ainda mostrar código antigo:
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 2. Verificar imagem Docker
docker images | grep medsafe-api

# Se imagem antiga (>1 hora):
docker rmi medsafe-api
docker-compose build --no-cache api
```

### **Se RAG ainda carregar 382k interações:**

```bash
# Verificar método find_interactions
docker exec medsafe_api grep -A 20 "def find_interactions" /app/backend/app/services/drug_interactions.py

# Deve mostrar:
# "BUSCA SOB DEMANDA - não carrega toda a base na memória"
# "with open(self.db_path, "r", encoding="utf-8") as f:"

# Se não mostrar, rebuild necessário:
docker-compose build --no-cache api
```

### **Se análise retornar risk_level="low" incorretamente:**

```bash
# Verificar logs detalhados
docker logs medsafe_api --tail 200 | grep -E "(Fenelzina|Ritalina|CRÍTICO|interações)"

# Deve mostrar:
# "✅ Interação encontrada: Fenelzina + Ritalina (critical)"
# "🔴 RISCO CRÍTICO identificado"

# Se não mostrar, verificar normalização de nomes:
docker exec medsafe_api python3 -c "
from backend.app.services.drug_interactions import get_interaction_service
service = get_interaction_service()
print(service._normalize_drug_name('Ritalina'))
print(service._normalize_drug_name('Fenelzina'))
"

# Output esperado:
# methylphenidate
# phenelzine
```

---

## 📈 Prevenção Futura

### **Opção 1: Development com Volume Mount**

**Modificar `docker-compose.yml` para dev:**
```yaml
services:
  api:
    volumes:
      - ./backend:/app/backend  # ← Código atualizado em tempo real
      - ./frontend:/app/frontend
      - ./logs:/app/logs
      - ./data:/app/data
```

**Vantagem:**
- Mudanças em Python refletem automaticamente (sem rebuild)
- Restart rápido: `docker-compose restart api` (2 segundos)

**Desvantagem:**
- Pode ter problemas de permissão
- Não funciona para mudanças em `requirements.txt`

### **Opção 2: CI/CD com rebuild automático**

**`.github/workflows/rebuild-on-code-change.yml`:**
```yaml
name: Rebuild on Code Change

on:
  push:
    paths:
      - 'backend/**'
      - 'frontend/**'

jobs:
  rebuild:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Rebuild Docker image
        run: docker-compose build --no-cache api
```

### **Opção 3: Watchdog para rebuild automático (local)**

**Script `scripts/auto-rebuild.sh`:**
```bash
#!/bin/bash
# Auto-rebuild quando arquivos Python mudarem

inotifywait -m -r -e modify backend/ |
while read path action file; do
    echo "Detected change: $file"
    docker-compose build api
    docker-compose restart api
done
```

---

## 📝 Resumo Executivo

| Etapa | Status | Tempo | Descrição |
|-------|--------|-------|-----------|
| **Diagnóstico** | ✅ | 1 min | Identificado Docker cache problem |
| **Parar API** | ✅ | 5 seg | `docker-compose stop api` |
| **Rebuild** | ✅ | 60 seg | `docker-compose build --no-cache api` |
| **Reiniciar** | ✅ | 15 seg | `docker-compose up -d api` |
| **Validar** | ✅ | 10 seg | Código atualizado confirmado |
| **Health** | ✅ | 5 seg | API saudável |

**Tempo total:** ~2 minutos

---

## 🎯 Próximo Teste Pelo Usuário

**O usuário deve agora:**
1. Acessar frontend: `http://localhost:9001`
2. Enviar análise: **Fenelzina + Ritalina**
3. Verificar resultado: **RISCO CRÍTICO** ✅
4. Conferir logs: Zero KeyErrors ✅

**Logs esperados (sucesso):**
```
🔍 Buscando interações para: Fenelzina
📊 Total de interações encontradas: 1 (escaneadas 191135 linhas)
🔴 RISCO CRÍTICO identificado
   - 1 interação(ões) crítica(s)
🧠 ClinicalAgent calling LLM...
💬 ClinicalAgent LLM responded: ### Clinical Recommendations...
✅ Análise concluída em 45s
   Risco: critical
   Interações: 1
   Confiança: 0.85
```

**Logs esperados (se ainda falhar):**
```
❌ Reportar ao desenvolvedor com logs completos
```

---

**Skills utilizadas:**
- @debugging-strategies (Docker cache diagnosis)
- @deployment-pipeline-design (Container rebuild strategy)
