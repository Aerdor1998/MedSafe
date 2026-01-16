# MedSafe - Sistema Inteligente de Contraindicacao de Medicamentos

Sistema de analise de contraindicacoes medicamentosas baseado em **Multi-Agent AI System** com LangGraph, Ollama (IA local), PostgreSQL e pgvector.

[![CI/CD](https://github.com/Aerdor1998/MedSafe/workflows/MedSafe%20CI%2FCD/badge.svg)](https://github.com/Aerdor1998/MedSafe/actions)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.50+-purple)]()
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)]()
[![Coverage](https://img.shields.io/badge/Coverage-%E2%89%A560%25-green)]()

## Funcionalidades

- **Multi-Agent AI System** (LangGraph) com 6 agentes especializados
- **RAG (Retrieval-Augmented Generation)** com documentacao medica
- **OCR de Prescricoes** com Tesseract + Vision AI
- **Base de Interacoes** com 191k+ interacoes medicamentosas
- **Safety Guardrails** com validacao em multiplas camadas
- **Human-in-the-Loop (HITL)** para aprovacao medica
- **Reflection Agent** para autocritica e melhoria continua
- **PostgreSQL + pgvector** para embeddings e busca semantica

## Quick Start

### Usando Docker (Recomendado)

```bash
# 1. Clonar repositorio
git clone https://github.com/Aerdor1998/MedSafe.git
cd MedSafe

# 2. Configurar variaveis de ambiente
cp env.example .env

# 3. Iniciar todos os servicos
./scripts/medsafe-full-start.sh

# 4. Verificar status
./scripts/docker-status.sh
```

**Endpoints:**
- **API**: http://localhost:9001
- **API Docs**: http://localhost:9001/docs
- **Health Check**: http://localhost:9001/healthz
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001

### Desenvolvimento Local

```bash
# 1. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar servicos necessarios
docker-compose up -d db redis

# 4. Iniciar aplicacao
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 9001
```

## Arquitetura

### Multi-Agent System (LangGraph)

```
START
  |
  v
+------------------+
|   TriageAgent    |  <- Valida entrada, extrai dados do paciente
+------------------+
  |
  v
+------------------+
|  DocumentAgent   |  <- RAG: busca evidencias medicas
+------------------+
  |
  v
+------------------+
|  ClinicalAgent   |  <- Analisa interacoes (191k+ regras)
+------------------+
  |
  v
+------------------+     +------------------+
| ReflectionAgent  | <-> |  ClinicalAgent   |  <- Loop de refinamento (max 3x)
+------------------+     +------------------+
  |
  v
+------------------+
|   SafetyAgent    |  <- Guardrails de seguranca
+------------------+
  |
  +---> requires_hitl? --YES--> +------------------+
  |                             |    HITLAgent     |  <- Revisao medica humana
  |                             +------------------+
  |                                      |
  +---> NO                               |
  |                                      |
  v                                      v
+------------------+
|    Finalize      |  <- Gera relatorio final
+------------------+
  |
  v
 END
```

### Stack Tecnologico

| Componente | Tecnologia | Versao |
|------------|-----------|--------|
| **Backend** | FastAPI | 0.115+ |
| **AI Framework** | LangGraph | 0.2.50+ |
| **LLM Local** | Ollama | qwen2.5:7b |
| **Database** | PostgreSQL + pgvector | 16+ |
| **Cache** | Redis | 7+ |
| **Observability** | Prometheus + Grafana | - |

### Estrutura do Projeto

```
MedSafe/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Configuracoes (Pydantic Settings)
│   │   ├── langgraph_agents/       # LangGraph Agents
│   │   │   ├── graph.py            # StateGraph workflow
│   │   │   ├── state.py            # Shared state
│   │   │   ├── base_agent.py       # Base class
│   │   │   ├── triage_agent.py     # Orchestrator
│   │   │   ├── document_agent.py   # RAG
│   │   │   ├── clinical_agent.py   # Clinical rules
│   │   │   ├── reflection_agent.py # Self-critique
│   │   │   ├── safety_agent.py     # Safety guardrails
│   │   │   └── hitl_agent.py       # Human-in-the-loop
│   │   ├── routers/                # API routes
│   │   ├── services/               # Business logic
│   │   ├── db/                     # Database layer
│   │   ├── auth/                   # Authentication (JWT + RBAC)
│   │   ├── middleware/             # HTTP middleware
│   │   ├── workers/                # Background workers
│   │   ├── utils/                  # Utilities
│   │   └── schemas/                # Pydantic models
│   └── tests/                      # Unit & integration tests
├── frontend/                       # SPA (HTML5 + Three.js)
├── alembic/                        # Database migrations
├── data/                           # Drug interactions CSV (191k+)
├── scripts/                        # Scripts utilitarios
├── infra/                          # Infrastructure configs
│   ├── prometheus/                 # Monitoring
│   └── monitoring/grafana/         # Dashboards
├── tests/e2e/                      # End-to-end tests
├── docker-compose.yml              # Development
├── docker-compose.prod.yml         # Production
├── Dockerfile                      # Production image
├── requirements.txt                # Python dependencies
└── README.md
```

## API Endpoints

### Analise de Medicamentos

```bash
POST /api/v2/triage
Content-Type: application/json

{
  "patient_data": {
    "age": 65,
    "weight": 70,
    "conditions": ["diabetes", "hypertension"]
  },
  "medications": ["Metformina", "Losartana", "AAS"]
}
```

### LangGraph Workflow

```bash
POST /api/v2/langgraph/analyze
Content-Type: application/json

{
  "medications": ["Aspirina", "Warfarina"],
  "patient_info": {...}
}
```

### Health Check

```bash
GET /healthz
GET /readyz
GET /livez
GET /metrics
```

Documentacao completa: http://localhost:9001/docs

## Testes

```bash
# Todos os testes
pytest backend/tests/ -v

# Com coverage
pytest backend/tests/ --cov=backend/app --cov-report=term-missing

# Testes E2E
pytest tests/e2e/ -v
```

## Variaveis de Ambiente

Principais variaveis (ver `env.example` para lista completa):

```env
# API
DEBUG=false
PORT=9001

# Database
DATABASE_URL=postgresql://medsafe:password@db:5432/medsafe

# Redis
REDIS_URL=redis://redis:6379/0

# Ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b

# Security
SECRET_KEY=your-secret-key-minimum-32-chars
JWT_SECRET=your-jwt-secret-minimum-32-chars
```

## Seguranca

- Autenticacao JWT com RBAC
- Rate limiting (slowapi + Redis)
- Security headers (CSP, HSTS, X-Frame-Options)
- Sanitizacao de inputs
- Logs de auditoria (LGPD compliant)
- Safety Guardrails em multiplas camadas
- Human-in-the-Loop para decisoes criticas

## CI/CD

O projeto usa GitHub Actions com os seguintes jobs:

- **Lint**: Black + isort + Flake8 + Bandit
- **Type Check**: MyPy
- **Unit Tests**: pytest com coverage >= 60%
- **Integration Tests**: Testes com PostgreSQL + Redis
- **Security Scan**: Safety + pip-audit + Bandit
- **Docker Build**: Build e scan de vulnerabilidades (Trivy)
- **E2E Tests**: Testes end-to-end (apenas em push para main)

## Licenca

MIT License

---

**Versao**: 1.0.0
**Atualizado**: 16/01/2026
**Mantido por**: Equipe MedSafe
