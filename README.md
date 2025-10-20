# MedSafe - MVP Microo SaaS

Sistema de análise de contraindicações medicamentosas com IA local, integração OpenFDA e PostgreSQL.

## 🚀 Funcionalidades

- ✅ Análise de contraindicações com IA (Ollama + Qwen)
- ✅ OCR de prescrições médicas (Tesseract + Vision AI)
- ✅ Integração com OpenFDA Drug Adverse Event API
- ✅ Banco de interações (191k+ interações do CSV)
- ✅ PostgreSQL com JSONB para dados estruturados
- ✅ Visualização 3D de interações medicamentosas
- ✅ Interface responsiva e moderna
- ✅ Logs de auditoria e compliance LGPD
- ✅ 55 testes unitários e de integração

## 📋 Requisitos

- Python 3.10+
- PostgreSQL 15+
- Docker & Docker Compose
- Tesseract OCR
- Ollama com modelos qwen3:4b e qwen2.5vl:7b

## ⚡ Quick Start

```bash
# 1. Clonar repositório
git clone https://github.com/Aerdor1998/MedSafe.git
cd MedSafe

# 2. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Iniciar PostgreSQL
docker run --name medsafe-postgres \
  -e POSTGRES_DB=medsafe \
  -e POSTGRES_USER=medsafe \
  -e POSTGRES_PASSWORD=medsafe123 \
  -p 5432:5432 -d postgres:15

# 5. Inicializar banco de dados
python3 -c "from backend.models.database import init_db; init_db()"

# 6. Iniciar aplicação
python3 backend/main.py
```

Acesse: **http://localhost:8050**

## 🏗️ Arquitetura

```
MedSafe/
├── backend/
│   ├── main.py                 # Entry point FastAPI (porta 8050)
│   ├── models/
│   │   ├── database.py         # PostgreSQL models
│   │   └── schemas.py          # Pydantic schemas
│   ├── services/
│   │   ├── ocr_service.py      # OCR + Vision
│   │   ├── ai_service.py       # Ollama integration
│   │   ├── drug_service.py     # Drug database
│   │   ├── openfda_service.py  # OpenFDA API ✨
│   │   ├── csv_service.py      # CSV interactions ✨
│   │   ├── vision_service.py   # Vision AI
│   │   └── logging_service.py  # Audit logs
│   └── tests/                  # 55 testes
├── frontend/
│   ├── index.html              # SPA
│   └── js/
│       ├── app.js              # Main logic
│       └── three-visualization.js  # 3D graphics
├── data/
│   └── db_drug_interactions.csv  # 191k+ interações
├── docker-compose.yml          # Production setup
└── requirements.txt            # Python deps
```

## 🔧 Configuração

### Variáveis de Ambiente

```env
# Backend
PORT=8050
DATABASE_URL=postgresql://medsafe:medsafe123@localhost:5432/medsafe

# Ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_TEXT_MODEL=qwen3:4b
OLLAMA_VISION_MODEL=qwen2.5vl:7b

# OpenFDA (opcional)
OPENFDA_API_KEY=your_key_here
```

### PostgreSQL Schema

```sql
CREATE TABLE medications (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    active_ingredient VARCHAR(255),
    contraindications JSONB,
    interactions JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
    id VARCHAR(255) PRIMARY KEY,
    patient_data JSONB,
    analysis_result JSONB,
    risk_level VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🧪 Testes

```bash
# Rodar todos os testes
pytest backend/tests/ -v

# Testes por categoria
pytest backend/tests/test_ocr.py -v
pytest backend/tests/test_ai_service.py -v
pytest backend/tests/test_integration.py -v

# Com coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

**Resultado**: 55/55 testes passando ✅

## 📊 API Endpoints

### Health Check
```bash
GET /api/health
```

### Análise de Medicamentos
```bash
POST /api/analyze
Content-Type: multipart/form-data

{
  "patient_data": {...},
  "medication_text": "Dipirona 500mg",
  "image": file.jpg  # opcional
}
```

### Busca de Medicamentos
```bash
GET /api/medications/search?q=dipirona
```

### OpenFDA Integration
```bash
GET /api/openfda/adverse-events?drug=aspirin
GET /api/openfda/drug-label?drug=ibuprofen
```

### Documentação Interativa
- Swagger UI: http://localhost:8050/docs
- ReDoc: http://localhost:8050/redoc

## 🐳 Docker

```bash
# Iniciar todos os serviços
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar serviços
docker-compose down
```

## 📈 Monitoramento

### Métricas
- Total de análises realizadas
- Contraindicações detectadas por severidade
- Tempo médio de processamento OCR
- Taxa de uso da API OpenFDA

### Logs
```bash
tail -f logs/medsafe.log
```

## 🔒 Segurança

- ✅ Autenticação JWT (em desenvolvimento)
- ✅ CORS configurado
- ✅ Sanitização de inputs
- ✅ Rate limiting (em desenvolvimento)
- ✅ Logs de auditoria LGPD
- ✅ Anonimização de dados antigos

## 🚢 Deploy

### Produção

```bash
# 1. Configurar variáveis de ambiente
cp env.example .env
# Editar .env com valores de produção

# 2. Build Docker
docker-compose -f docker-compose.prod.yml build

# 3. Deploy
docker-compose -f docker-compose.prod.yml up -d

# 4. Verificar saúde
curl https://medsafe.app/api/health
```

### Hugging Face Spaces

```bash
# Configurar secrets:
DATABASE_URL, OLLAMA_BASE_URL, SECRET_KEY

# Deploy automático via GitHub Actions
```

## 📚 Dados

### CSV Drug Interactions
- **Arquivo**: `data/db_drug_interactions.csv`
- **Registros**: 191,543 interações
- **Formato**: Drug 1, Drug 2, Interaction Description
- **Carregamento**: Automático na inicialização

### OpenFDA
- **Eventos Adversos**: Dados em tempo real
- **Bulas**: Informações oficiais da FDA
- **Recalls**: Alertas de segurança

## 🛣️ Roadmap

### Fase 1 - MVP ✅
- [x] OCR e análise de prescrições
- [x] PostgreSQL com pgvector
- [x] Integração OpenFDA
- [x] Interface 3D
- [x] 55 testes unitários

### Fase 2 - Produção
- [ ] Autenticação JWT completa
- [ ] Multi-tenancy (clínicas)
- [ ] Dashboard administrativo
- [ ] Exportação PDF
- [ ] Integração HL7/FHIR

### Fase 3 - Scale
- [ ] ML proprietário
- [ ] App mobile (React Native)
- [ ] Integração ANVISA
- [ ] Alertas em tempo real
- [ ] Análise de prontuários

## 📄 Licença

MIT License - veja LICENSE para detalhes

## 👥 Suporte

- **Email**: suporte@medsafe.com.br
- **Issues**: https://github.com/Aerdor1998/MedSafe/issues
- **Docs**: https://github.com/Aerdor1998/MedSafe/wiki

---

**Versão**: 1.0.0  
**Última atualização**: 01/10/2025  
**Mantido por**: Equipe MedSafe
