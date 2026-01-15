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

- **Multi-Agent AI System** (LangGraph Level 3) com 6 agentes especializados
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

## Índice

- [Quick Start](#-quick-start)
- [Arquitetura](#-arquitetura)
- [Documentação](#-documentação)
- [Scripts Utilitários](#-scripts-utilitários)
- [Desenvolvimento](#-desenvolvimento)
- [Deploy](#-deploy)
- [Testes](#-testes)

## Quick Start

### Usando Docker (Recomendado)

```bash
# 1. Clonar repositório
git clone https://github.com/Aerdor1998/MedSafe.git
cd MedSafe

# 2. Configurar variáveis de ambiente
cp env.example .env

# 3. Iniciar todos os serviços
./scripts/docker-start.sh

# 4. Verificar status
./scripts/docker-status.sh

# 5. Ver logs
./scripts/docker-logs.sh
```

Acesse:
- **Frontend**: http://localhost:9000
- **API Docs**: http://localhost:9000/docs
- **Health Check**: http://localhost:9000/healthz

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
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 9000
```

## Arquitetura

### Multi-Agent System (LangGraph)

MedSafe implementa uma **arquitetura Level 3** de múltiplos agentes colaborativos:

```
┌─────────────────────────────────────────────────────────────┐
│                    CaptainAgent (Orchestrator)               │
│         Com Safety Guardrails + HITL + Reflection           │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
  ┌─────▼──────┐                      ┌──────▼──────┐
  │ VisionAgent│                      │  DocAgent   │
  │  (OCR)     │                      │   (RAG)     │
  └─────┬──────┘                      └──────┬──────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                  ┌────────▼─────────┐
                  │  ClinicalRules   │
                  │  Agent (191k+)   │
                  └────────┬─────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
  ┌─────▼──────────┐              ┌──────────▼────────┐
  │ SafetyGuardrails│              │ ReflectionAgent   │
  │    Agent        │              │ (Self-Critique)   │
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
| **Observability** | OpenTelemetry | 1.29+ |
| **Frontend** | HTML5 + Three.js | - |

### Estrutura do Projeto

```
MedSafe/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Configurações
│   │   ├── agents/                    # AG2 Agents (legacy)
│   │   │   ├── orchestrator.py        # CaptainAgent
│   │   │   ├── vision.py              # OCR + Vision
│   │   │   ├── docagent.py            # RAG Agent
│   │   │   ├── clinical.py            # Clinical Rules
│   │   │   ├── safety_guardrails.py   # Safety Agent
│   │   │   ├── human_in_the_loop.py   # HITL Agent
│   │   │   └── reflection_agent.py    # Reflection Agent
│   │   ├── langgraph_agents/          # LangGraph Agents (new)
│   │   │   ├── state.py               # Shared state
│   │   │   ├── graph.py               # StateGraph
│   │   │   ├── checkpointing.py       # PostgreSQL checkpointer
│   │   │   └── [agents].py            # Individual agents
│   │   ├── routers/                   # API routes (planned)
│   │   ├── services/                  # Business logic
│   │   │   ├── drug_interactions.py   # 191k+ interactions
│   │   │   └── interaction_classifier.py
│   │   ├── db/                        # Database layer
│   │   │   ├── database.py            # SQLAlchemy setup
│   │   │   └── models.py              # ORM models
│   │   ├── utils/                     # Utilities
│   │   │   └── logging_config.py      # Structured logging
│   │   └── schemas.py                 # Pydantic models
│   └── tests/                         # Unit + Integration tests
├── frontend/
│   ├── index.html                     # SPA
│   └── js/
│       ├── app.js                     # Main logic
│       └── three-visualization.js     # 3D graphics
├── data/
│   └── db_drug_interactions.csv       # 191k+ interações
├── docs/                              # Documentação (organizada)
│   ├── guides/                        # Guias de uso
│   ├── architecture/                  # Arquitetura e análises
│   ├── deployment/                    # Deploy guides
│   ├── fixes/                         # Histórico de fixes
│   ├── roadmap/                       # Roadmaps e planejamento
│   └── setup/                         # Setup e configuração
├── scripts/                           # Scripts utilitários
│   ├── docker-start.sh                # Inicia containers
│   ├── docker-stop.sh                 # Para containers
│   ├── docker-status.sh               # Verifica status
│   └── docker-logs.sh                 # Visualiza logs
├── logs/                              # Application logs
├── static/                            # Static files
├── docker-compose.yml                 # Docker Compose
├── Dockerfile                         # Production image
├── requirements.txt                   # Python dependencies
├── env.example                        # Environment template
└── README.md                          # Este arquivo
```

## Documentação

A documentação está organizada em categorias para facilitar a navegação:
Observação: a pasta `docs/` é mantida localmente e está no `.gitignore`.

### Guias de Uso

- [Como Usar o Sistema](docs/guides/COMO_USAR.md) - Tutorial completo
- [Configuração de Modelos](docs/guides/CONFIGURACAO_MODELOS.md) - Setup Ollama
- [Testes de Interações](docs/guides/TESTES_INTERACOES.md) - Como testar

### Arquitetura

- [Análise de Arquitetura](docs/architecture/MEDSAFE_ARCHITECTURE_ANALYSIS.md) - Análise profunda (31 KB)
- [Sumário Executivo](docs/architecture/MEDSAFE_ARCHITECTURE_SUMMARY.md) - Overview (7.8 KB)
- [Referência Rápida](docs/architecture/ANALYSIS_QUICK_REFERENCE.txt) - Cartão de referência
- [Migração LangGraph](docs/architecture/LANGGRAPH_MIGRATION.md) - Detalhes da migração
- [Safety Improvements](docs/architecture/SAFETY_IMPROVEMENTS.md) - Melhorias de segurança

### Deploy e Setup

- [Guia de Deploy](docs/deployment/DEPLOYMENT_GUIDE.md) - Deploy em produção
- [Deploy Success](docs/deployment/DEPLOYMENT_SUCCESS.md) - Checklist de sucesso
- [Docker Setup](docs/setup/README_DOCKER.md) - Configuração Docker
- [Testing Guide](docs/setup/TESTING_GUIDE.md) - Como testar
- [Logging Guide](docs/setup/LOGGING_GUIDE.md) - Sistema de logs

### Roadmap

- [Roadmap Produção](docs/roadmap/MEDSAFE_PRODUCTION_ROADMAP.md) - Planejamento completo
- [Fase 1-2 Complete](docs/roadmap/FASE_1-2_COMPLETE.md) - Status atual
- [Roadmap Fase 3-6](docs/roadmap/ROADMAP_FASE_3-6.md) - Próximas fases

### Histórico de Fixes

Ver [docs/fixes/](docs/fixes/) para histórico detalhado de correções e melhorias.

## Scripts Utilitários

Scripts disponíveis em `scripts/`:

```bash
# Docker Management
./scripts/docker-start.sh           # Inicia todos os containers
./scripts/docker-stop.sh            # Para todos os containers
./scripts/docker-status.sh          # Verifica status dos serviços
./scripts/docker-logs.sh            # Mostra logs em tempo real
./scripts/docker-troubleshoot.sh    # Troubleshooting automático

# Network Management
./scripts/docker-fix-network.sh     # Corrige problemas de rede
./scripts/docker-clean-networks.sh  # Limpa redes não utilizadas

# Application
./scripts/start.sh                  # Start app (legacy)
./scripts/stop.sh                   # Stop app (legacy)
./scripts/status.sh                 # Check status
```

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
PORT=9000

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
curl http://localhost:9000/healthz

# 4. Ver logs
docker-compose logs -f medsafe_api
```

### Health Checks

O sistema expõe os seguintes endpoints de monitoramento:

- `GET /healthz` - Health check geral
- `GET /readyz` - Readiness probe (Kubernetes)
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
```

## API Endpoints

### Análise de Medicamentos

```bash
POST /api/triage
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
POST /api/vision/analyze
Content-Type: multipart/form-data

{
  "image": <file>,
  "patient_context": {...}
}
```

Documentação completa: http://localhost:9000/docs

## Skills Aplicadas

Este projeto utiliza as seguintes skills profissionais:

- **@debugging-strategies** - Debugging sistemático e análise de root cause
- **@api-design-principles** - Design de APIs RESTful
- **@code-review-excellence** - Code review e qualidade de código
- **@python-performance-optimization** - Otimização de performance
- **@python-testing-patterns** - Padrões de teste com pytest
- **@fastapi-templates** - Templates FastAPI production-ready

## Segurança

- ✅ Autenticação JWT (em desenvolvimento)
- ✅ CORS configurado
- ✅ Sanitização de inputs
- ✅ Rate limiting (planejado)
- ✅ Logs de auditoria LGPD
- ✅ Anonimização automática
- ✅ Safety Guardrails em múltiplas camadas
- ✅ Human-in-the-Loop para decisões críticas

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

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes

## Suporte

- **Documentação**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/Aerdor1998/MedSafe/issues)
- **Email**: suporte@medsafe.com.br

---

**Versão**: 1.0.0
**Última atualização**: 13/11/2025
**Status**: Production Ready (7/10)
**Mantido por**: Equipe MedSafe
