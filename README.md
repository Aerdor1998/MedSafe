# MedSafe - Sistema Inteligente de Contraindicação de Medicamentos

Sistema de análise de contraindicações medicamentosas baseado em **Multi-Agent AI System** com LangGraph, Ollama (IA local), PostgreSQL e pgvector.

[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()
[![Python](https://img.shields.io/badge/Python-3.10+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-purple)]()
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)]()
[![codecov](https://codecov.io/gh/Aerdor1998/MedSafe/branch/main/graph/badge.svg)](https://codecov.io/gh/Aerdor1998/MedSafe)
[![Coverage](https://img.shields.io/badge/Coverage-%E2%89%A570%25-green)]()
[![CI](https://github.com/Aerdor1998/MedSafe/workflows/CI%20-%20MedSafe%20Tests%20%26%20Coverage/badge.svg)](https://github.com/Aerdor1998/MedSafe/actions)

## Funcionalidades

- **Multi-Agent AI System** (LangGraph Level 3) com 7 agentes especializados
- **RAG (Retrieval-Augmented Generation)** com documentação médica OMS/ANVISA
- **OCR de Prescrições** com Tesseract + Vision AI (Qwen2.5-VL)
- **Base de Interações** com 191k+ interações medicamentosas
- **Safety Guardrails** com validação em múltiplas camadas
- **Human-in-the-Loop (HITL)** para aprovação médica
- **Reflection Agent** para autocrítica e melhoria contínua
- **PostgreSQL + pgvector** para embeddings e busca semântica
- **Visualização 3D** de interações medicamentosas
- **Logging Estruturado** com OpenTelemetry
- **Compliant LGPD** com auditoria e anonimização
- **Workers Assíncronos** para processamento em background

## Índice

- [Quick Start](#quick-start)
- [Arquitetura](#arquitetura)
- [Scripts Utilitários](#scripts-utilitários)
- [Desenvolvimento](#desenvolvimento)
- [Deploy](#deploy)
- [Testes](#testes)
- [API Endpoints](#api-endpoints)
- [Segurança](#segurança)

## Quick Start

### Usando Docker (Recomendado)

```bash
# 1. Clonar repositório
git clone https://github.com/Aerdor1998/MedSafe.git
cd MedSafe

# 2. Configurar variáveis de ambiente
cp env.example .env

# 3. Iniciar todos os serviços (recomendado)
./scripts/medsafe-full-start.sh

# 4. Verificar status
./scripts/docker-status.sh

# 5. Ver logs
./scripts/docker-logs.sh
```

Acesse:
- **Frontend**: http://localhost:9001
- **API Docs**: http://localhost:9001/docs
- **Health Check**: http://localhost:9001/healthz
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001

### Desenvolvimento Local

```bash
# 1. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Iniciar serviços necessários
docker-compose up -d medsafe_db medsafe_ollama

# 4. Configurar banco de dados
python3 -c "from backend.app.db.database import init_db; init_db()"

# 5. Iniciar aplicação
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 9001
```

## Arquitetura

### Multi-Agent System (LangGraph)

MedSafe implementa uma **arquitetura Level 3** de múltiplos agentes colaborativos:

```
┌─────────────────────────────────────────────────────────────┐
│                    TriageAgent (Orchestrator)               │
│         Com Safety Guardrails + HITL + Reflection           │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
  ┌─────▼──────┐                      ┌──────▼──────┐
  │ VisionAgent│                      │ DocumentAgent│
  │  (OCR/VLM) │                      │   (RAG)      │
  └─────┬──────┘                      └──────┬───────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                  ┌────────▼─────────┐
                  │  ClinicalAgent   │
                  │  (Rules 191k+)   │
                  └────────┬─────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
  ┌─────▼──────────┐              ┌──────────▼────────┐
  │  SafetyAgent   │              │ ReflectionAgent   │
  │  (Guardrails)  │              │ (Self-Critique)   │
  └─────┬──────────┘              └──────────┬────────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                  ┌────────▼─────────┐
                  │   HITL Agent     │
                  │ (Human Approval) │
                  └──────────────────┘
```

### Stack Tecnológico

| Componente | Tecnologia | Versão |
|------------|-----------|--------|
| **Backend** | FastAPI | 0.115+ |
| **AI Framework** | LangGraph | 1.0+ |
| **LLM Local** | Ollama (Qwen2.5) | 7B |
| **Database** | PostgreSQL + pgvector | 15+ |
| **OCR** | Tesseract + Vision AI | - |
| **Observability** | OpenTelemetry + Prometheus | 1.29+ |
| **Frontend** | HTML5 + Three.js | - |
| **Monitoring** | Grafana | 10+ |

### Estrutura do Projeto

```
MedSafe/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Configurações (Pydantic Settings)
│   │   ├── agents/                    # Agents auxiliares
│   │   │   └── vision.py              # OCR + Vision helpers
│   │   ├── langgraph_agents/          # LangGraph Agents (principal)
│   │   │   ├── state.py               # Shared state
│   │   │   ├── graph.py               # StateGraph workflow
│   │   │   ├── checkpointing.py       # PostgreSQL checkpointer
│   │   │   ├── base_agent.py          # Base class
│   │   │   ├── triage_agent.py        # Orchestrator
│   │   │   ├── vision_agent.py        # OCR/VLM
│   │   │   ├── document_agent.py      # RAG
│   │   │   ├── clinical_agent.py      # Clinical rules
│   │   │   ├── safety_agent.py        # Safety guardrails
│   │   │   ├── reflection_agent.py    # Self-critique
│   │   │   └── hitl_agent.py          # Human-in-the-loop
│   │   ├── routers/                   # API routes
│   │   │   ├── admin.py               # Admin endpoints
│   │   │   ├── auth.py                # Authentication
│   │   │   ├── health.py              # Health checks
│   │   │   ├── human_review.py        # HITL review
│   │   │   ├── langgraph.py           # LangGraph workflow
│   │   │   ├── medications.py         # Drug interactions
│   │   │   ├── monitoring.py          # Metrics
│   │   │   └── vision.py              # OCR endpoints
│   │   ├── services/                  # Business logic
│   │   │   ├── analysis_orchestrator.py
│   │   │   ├── clinical_rules.py
│   │   │   ├── drug_identifier.py
│   │   │   ├── drug_interactions.py   # 191k+ interactions
│   │   │   ├── interaction_classifier.py
│   │   │   ├── literature_ingestion.py
│   │   │   ├── openfda_service.py
│   │   │   └── response_formatter.py
│   │   ├── db/                        # Database layer
│   │   │   ├── database.py            # SQLAlchemy setup
│   │   │   ├── models.py              # ORM models
│   │   │   ├── user_models.py         # User/Auth models
│   │   │   ├── vector_store.py        # pgvector store
│   │   │   └── migrations/            # SQL migrations
│   │   ├── auth/                      # Authentication
│   │   │   ├── jwt.py                 # JWT handling
│   │   │   ├── password.py            # Password hashing
│   │   │   ├── models.py              # Auth models
│   │   │   └── rbac.py                # Role-based access
│   │   ├── middleware/                # HTTP middleware
│   │   │   ├── logging.py             # Request logging
│   │   │   ├── metrics.py             # Prometheus metrics
│   │   │   ├── rate_limit.py          # Rate limiting
│   │   │   ├── security.py            # Security headers
│   │   │   ├── prometheus.py          # Prometheus integration
│   │   │   └── request_id.py          # Correlation IDs
│   │   ├── workers/                   # Background workers
│   │   │   ├── analysis_worker.py     # Async analysis
│   │   │   └── data_retention_worker.py # LGPD compliance
│   │   ├── utils/                     # Utilities
│   │   │   ├── logging_config.py      # Structured logging
│   │   │   ├── audit_logger.py        # Audit trail
│   │   │   ├── cache.py               # Caching
│   │   │   ├── circuit_breaker.py     # Resilience
│   │   │   ├── data_retention.py      # LGPD utils
│   │   │   └── file_upload.py         # File handling
│   │   └── schemas/                   # Pydantic models
│   │       ├── base.py
│   │       ├── medications.py
│   │       ├── triage.py
│   │       ├── vision.py
│   │       └── reports.py
│   └── tests/                         # 40+ test files
├── frontend/
│   ├── index.html                     # SPA
│   └── js/
│       ├── app.js                     # Main logic
│       ├── medsafe-api.js             # API client
│       └── tailwind-config.js         # Styling
├── alembic/                           # Database migrations
│   └── versions/                      # 7 migration files
├── data/
│   └── db_drug_interactions.csv       # 191k+ interações
├── scripts/                           # Scripts utilitários
│   ├── medsafe-full-start.sh          # Start completo
│   ├── medsafe-full-stop.sh           # Stop completo
│   ├── docker-start.sh                # Start Docker
│   ├── docker-stop.sh                 # Stop Docker
│   ├── docker-status.sh               # Status
│   ├── docker-logs.sh                 # Logs
│   ├── apply-db-indexes.sh            # DB indexes
│   ├── db-backup.sh                   # Backup
│   ├── security_check.py              # Security audit
│   └── README.md                      # Scripts docs
├── infra/
│   ├── nginx/nginx.conf               # Reverse proxy
│   ├── prometheus/                    # Monitoring config
│   ├── monitoring/grafana/            # Dashboards
│   └── ollama/                        # Ollama config
├── tests/
│   └── e2e/                           # End-to-end tests
├── docker-compose.yml                 # Development
├── docker-compose.prod.yml            # Production
├── docker-compose.monitoring.yml      # Monitoring stack
├── Dockerfile                         # Production image
├── requirements.txt                   # Python dependencies
├── requirements-test.txt              # Test dependencies
├── env.example                        # Environment template
├── env.prod.example                   # Production template
├── pytest.ini                         # Pytest config
├── alembic.ini                        # Alembic config
└── README.md                          # Este arquivo
```

## Scripts Utilitários

Scripts disponíveis em `scripts/`:

```bash
# Full Stack Management
./scripts/medsafe-full-start.sh        # Inicia TUDO (recomendado)
./scripts/medsafe-full-stop.sh         # Para TUDO

# Docker Management
./scripts/docker-start.sh              # Inicia containers core
./scripts/docker-stop.sh               # Para containers
./scripts/docker-status.sh             # Verifica status
./scripts/docker-logs.sh               # Mostra logs
./scripts/docker-troubleshoot.sh       # Troubleshooting

# Database
./scripts/apply-db-indexes.sh          # Aplica indexes
./scripts/db-backup.sh                 # Backup do banco
./scripts/db-migrate.sh                # Rodar migrations

# Security
python scripts/security_check.py       # Auditoria de segurança
```

Ver [scripts/README.md](scripts/README.md) para documentação completa.

## Desenvolvimento

### Requisitos

- Python 3.10+
- Docker & Docker Compose
- Ollama com modelos:
  - `qwen2.5:7b` (texto)
  - `qwen2.5vl:7b` (visão)
- PostgreSQL 15+ com pgvector

### Configuração de Desenvolvimento

```bash
# 1. Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Baixar modelos
ollama pull qwen2.5:7b
ollama pull qwen2.5vl:7b

# 3. Setup ambiente
cp env.example .env
# Editar .env conforme necessário

# 4. Instalar dependências
pip install -r requirements.txt
pip install -r requirements-test.txt

# 5. Rodar testes
pytest backend/tests/ -v
```

### Variáveis de Ambiente

Ver [env.example](env.example) para lista completa. Principais:

```env
# API
APP_NAME=MedSafe
APP_VERSION=1.0.0
DEBUG=true
PORT=9001

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medsafe
POSTGRES_USER=medsafe
POSTGRES_PASSWORD=medsafe123

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_TEXT_MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=qwen2.5vl:7b

# Security
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Logging
LOG_LEVEL=INFO
```

## Deploy

### Deploy com Docker (Produção)

```bash
# 1. Build imagem
docker-compose -f docker-compose.prod.yml build

# 2. Iniciar serviços
docker-compose -f docker-compose.prod.yml up -d

# 3. Verificar health
curl http://localhost:9001/healthz

# 4. Ver logs
docker-compose logs -f medsafe_api
```

### Health Checks

O sistema expõe os seguintes endpoints de monitoramento:

- `GET /healthz` - Health check geral
- `GET /readyz` - Readiness probe (Kubernetes)
- `GET /livez` - Liveness probe (Kubernetes)
- `GET /metrics` - Métricas Prometheus

## Testes

```bash
# Rodar todos os testes
pytest backend/tests/ -v

# Com coverage
pytest backend/tests/ --cov=backend --cov-report=html

# Testes específicos
pytest backend/tests/test_langgraph_workflow.py -v
pytest backend/tests/test_safety_guardrails.py -v
pytest backend/tests/test_config.py -v

# Testes E2E
pytest tests/e2e/ -v
```

## API Endpoints

### Análise de Medicamentos

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

### OCR de Prescrições

```bash
POST /api/v2/vision/analyze
Content-Type: multipart/form-data

{
  "image": <file>,
  "patient_context": {...}
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

Documentação completa: http://localhost:9001/docs

## Segurança

- ✅ Autenticação JWT com RBAC
- ✅ CORS configurado (sem wildcard em produção)
- ✅ Sanitização de inputs
- ✅ Rate limiting
- ✅ Logs de auditoria LGPD
- ✅ Anonimização automática (data retention worker)
- ✅ Safety Guardrails em múltiplas camadas
- ✅ Human-in-the-Loop para decisões críticas
- ✅ SQL Injection prevention (queries parametrizadas)
- ✅ Security headers (CSP, HSTS, etc.)

## Monitoramento

### Logs

```bash
# Logs da aplicação
tail -f logs/medsafe.log

# Logs Docker
docker-compose logs -f medsafe_api

# Logs estruturados (JSON)
grep "ERROR" logs/medsafe.log | jq
```

### Métricas

- Total de análises realizadas
- Contraindicações detectadas por severidade
- Tempo médio de processamento
- Taxa de aprovação HITL
- Accuracy do Reflection Agent

### Grafana Dashboards

Acesse http://localhost:3001 (admin/medsafe2025):
- MedSafe Overview
- HITL Dashboard
- Performance Optimization

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes

## Suporte

- **Issues**: [GitHub Issues](https://github.com/Aerdor1998/MedSafe/issues)
- **Email**: suporte@medsafe.com.br

---

**Versão**: 1.0.0
**Última atualização**: 15/01/2026
**Status**: Production Ready (8/10)
**Mantido por**: Equipe MedSafe
