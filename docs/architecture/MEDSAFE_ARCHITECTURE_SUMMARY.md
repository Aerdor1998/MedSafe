# SUMÁRIO EXECUTIVO - Análise Arquitetural MedSafe

## Status Geral: ✅ BOM (7/10)

---

## 🏗️ ARQUITETURA

### Tipo: Multi-Agent System (LangGraph) + Legado (AG2)
- **Frontend:** HTML5/JS + Three.js para 3D
- **API:** FastAPI (9000/9001)
- **Agents:** 6 LangGraph + 6 AG2 (coexistentes)
- **Data:** PostgreSQL 15+ pgvector
- **IA Local:** Ollama (qwen2.5:7b LLM, qwen2.5vl:7b VLM)
- **OCR:** Tesseract (POR+ENG)

### Camadas:
```
Frontend (SPA)
    ↓
API Layer (FastAPI + Routers)
    ↓
Business Logic (Agents + Services)
    ↓
Data Layer (SQLAlchemy + PostgreSQL)
```

---

## 🗂️ ESTRUTURA DO PROJETO

| Componente | Arquivos | Linhas | Status |
|-----------|----------|--------|--------|
| **Agentes AG2** | 6 | ~1.5k | Legado |
| **Agentes LangGraph** | 12 | ~2k | Novo |
| **Routers** | 3 | ~15k | Inline no main.py ⚠️ |
| **Schemas** | 6 | ~500 | ✅ |
| **Services** | 2 | ~600 | ✅ |
| **Database** | 2 | ~300 | ✅ |
| **Middleware** | 5 | ~200 | ✅ |
| **Utils** | 4+ | ~150 | ✅ |
| **Tests** | 10+ | - | Presente |
| **TOTAL** | 60+ | 10.2k | ✅ |

---

## ⚠️ PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. LangGraph Import Falha ❌ (ALTA)
```
ModuleNotFoundError: No module named 'langgraph'
Localização: backend/app/langgraph_agents/__init__.py:31
```
**Solução:** Garantir `pip install -r requirements.txt` antes de usar

---

### 2. Routers Inline no main.py ⚠️ (MÉDIA)
```python
# Problema: Routers definidos em main.py ao invés de routers/
# Causado por: Import circular no Docker
# Violação: Padrão de organização
# Linha 105-183: Código health endpoints duplicado
```
**Impacto:** Difícil manutenção, viola padrões

---

### 3. Dois Sistemas Coexistindo ⚠️ (MÉDIA)
```
backend/app/
├── agents/            # AG2 (legado, em uso)
├── langgraph_agents/  # LangGraph (novo, recomendado)
```
**Status:** Documentado em LANGGRAPH_MIGRATION.md
**Recomendação:** Deprecar AG2 e migrar completamente

---

### 4. Configuração Duplicada ⚠️ (BAIXA)
```
env.example:
- Linhas 1-89: Template padrão
- Linhas 89-154: Valores desenvolvimento (duplicado)
```

---

### 5. Portas Inconsistentes ⚠️ (BAIXA)
| Sistema | Porta |
|---------|-------|
| docker-compose.yml | 9000 |
| main.py | 9000 |
| run.py | 9001 |

---

## ✅ PONTOS FORTES

| Aspecto | Avaliação | Detalhe |
|--------|-----------|--------|
| **Separação de Camadas** | ✅✅✅ | API, Business, Data bem definidas |
| **Type Hints** | ✅✅✅ | Usando `Dict[str, Any]`, `Optional`, etc |
| **Logging** | ✅✅✅ | Estruturado, JSON format, cores |
| **Security** | ✅✅ | JWT, bcrypt, CORS, env validation |
| **Database** | ✅✅✅ | SQLAlchemy ORM, migrations, pgvector |
| **Testing** | ✅✅ | pytest, conftest, fixtures presentes |
| **Docker** | ✅✅✅ | Dockerfile profissional, compose, healthchecks |
| **Error Handling** | ✅✅ | Try/catch genéricos, poderia ser específico |

---

## ❌ PONTOS FRACOS

| Aspecto | Avaliação | Detalhe |
|--------|-----------|--------|
| **Organização** | ⚠️⚠️ | Routers inline, config grande |
| **Documentação** | ⚠️⚠️ | Dispersa em 20+ .md files |
| **Tamanho dos Arquivos** | ⚠️ | main.py: 546 linhas, muito grande |
| **Importações** | ⚠️ | LangGraph não garantido, config imports |
| **Pattern Factory** | ❌ | Sem factory para criar agentes |
| **Cobertura de Testes** | ❓ | Presente mas cobertura desconhecida |

---

## 🔄 FLUXO DE REQUISIÇÃO

```
POST /api/v1/triage
    ↓
[CORS, Logging, Rate Limit Middleware]
    ↓
[Pydantic Validation]
    ↓
Background Task:
    ├→ Save Triage (DB)
    ├→ VisionAgent (OCR) → Extract Drug Name
    ├→ DocAgent (RAG) → Fetch Evidence
    ├→ ClinicalAgent → Analyze
    ├→ ReflectionAgent → Refine (Loop max 3x)
    ├→ SafetyAgent → Validate
    ├→ HITLAgent (if needed) → Wait Approval
    └→ Save Report (DB)
    ↓
Response: {status, risk_level, interactions, ...}
```

---

## 📊 DEPENDÊNCIAS

### Core
- **langgraph** >=0.2.50 (Multi-agent)
- **langchain** >=0.3.0 (LLM framework)
- **fastapi** >=0.115.0 (API)
- **sqlalchemy** >=2.0.0 (ORM)
- **pydantic** >=2.0.0 (Validation)
- **psycopg2** + **pgvector** (PostgreSQL + vectors)

### IA/ML
- **ollama** >=0.5.0 (Local LLM)
- **openai** (Fallback)
- **numpy, scikit-learn** (Math)

### Observabilidade
- **prometheus-client** (Metrics)
- **structlog** (Logging)
- **opentelemetry** (Tracing)

### Sistema (Dockerfile)
- **tesseract-ocr** + **tesseract-ocr-por**
- **libpq-dev** (PostgreSQL client)
- **gcc** (C compiler)

---

## 🎯 RECOMENDAÇÕES (Prioridade)

### 🔴 ALTA PRIORIDADE
1. **Remover Routers Inline** (Impacto: Manutenibilidade)
   - Debugar por que imports circulares no Docker
   - Mover health, langgraph, human_review para routers/

2. **Clarificar Qual Sistema Usar** (Impacto: Confusão)
   - Documentar: AG2 vs LangGraph quando usar cada um
   - Deprecation timeline para AG2

3. **Dividir config.py** (Impacto: Manutenibilidade)
   - De 136 linhas para múltiplos módulos
   - database.py, security.py, api.py, ai.py

### 🟡 MÉDIA PRIORIDADE
4. **Agent Factory** - Facilitar testes e switchable
5. **Consolidar Logging** - Integrar OpenTelemetry
6. **Cleanup env.example** - Remover duplicação

### 🟢 BAIXA PRIORIDADE
7. **Refatorar main.py** - Quebrar em funções
8. **Pre-commit Hooks** - black, isort, pylint, mypy
9. **Documentação Consolidada** - Architecture diagrams

---

## 📈 MÉTRICAS

```
Qualidade Geral: 7/10
├── Arquitetura: 8/10 ✅
├── Segurança: 7/10 ✅
├── Logging: 9/10 ✅
├── Testing: 6/10 ⚠️
├── Documentação: 5/10 ❌
└── Manutenibilidade: 6/10 ⚠️
```

---

## 🚀 COMEÇAR A USAR

### Setup Local
```bash
# 1. Environment
cp env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'  # SECRET_KEY
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'  # JWT_SECRET

# 2. Dependencies
pip install -r requirements.txt

# 3. Database (PostgreSQL local)
# Editar .env com POSTGRES_HOST=localhost

# 4. Ollama
ollama pull qwen2.5:7b
ollama pull qwen2.5vl:7b

# 5. Run
python3 run.py  # Porta 9001
```

### Setup Docker
```bash
# Build and run
docker-compose up -d

# Verificar
curl http://localhost:9000/healthz
```

---

## 📚 DOCUMENTAÇÃO PROJETO

- **MEDSAFE_ARCHITECTURE_ANALYSIS.md** (Este arquivo gerado)
- **LANGGRAPH_MIGRATION.md** - Migração do AG2
- **CIRCULAR_IMPORT_FIX.md** - Histórico de fixes
- **ROUTER_IMPORT_ISSUE.md** - Problema com routers
- **DEPLOYMENT_GUIDE.md** - Deploy em produção
- **LOGGING_GUIDE.md** - Logging estruturado
- **+ 15 documentos** descrevendo changes

---

## 👥 PARA NOVOS DESENVOLVEDORES

**Estrutura Básica:**
```
MedSafe/
├── frontend/           # HTML5 + JS (start here for UI)
├── backend/
│   └── app/
│       ├── main.py     # Entry point (API)
│       ├── agents/     # Legado (não usar novo código)
│       ├── langgraph_agents/ # NOVO (usar para novos features)
│       ├── services/   # Lógica de negócio
│       ├── schemas/    # Modelos Pydantic
│       └── db/         # Database layer
└── docker-compose.yml  # Local development
```

**Fluxo Recomendado:**
1. Entender o LangGraph StateGraph (langgraph_agents/state.py)
2. Entender os Agents (triage_agent.py, clinical_agent.py, etc)
3. Entender os Schemas (schemas/triage.py, etc)
4. Fazer mudanças em langgraph_agents/, NÃO em agents/ (legado)

---

## ✨ CONCLUSÃO

O MedSafe é um **projeto bem estruturado** com **boa arquitetura** mas precisa de **limpeza de código** e **consolidação de documentação**. A transição de AG2 para LangGraph está em progresso e requer maior clareza sobre quando usar cada sistema.

**Score: 7/10** - Pronto para produção com pequitas melhorias recomendadas.
