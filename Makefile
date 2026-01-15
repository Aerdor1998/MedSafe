# MedSafe - Makefile para operações
# Uso: make <comando>

.PHONY: help dev test lint fmt migrate ingest reindex clean build up down logs

# Variáveis
COMPOSE_FILE = docker-compose.yml
PYTHON = python3
PIP = pip3

# Comando padrão
help:
	@echo "MedSafe - Comandos disponíveis:"
	@echo ""
	@echo "Desenvolvimento:"
	@echo "  dev         - Iniciar ambiente de desenvolvimento"
	@echo "  build       - Construir imagens Docker"
	@echo "  up          - Subir serviços com Docker Compose"
	@echo "  down        - Parar serviços"
	@echo "  logs        - Ver logs dos serviços"
	@echo ""
	@echo "Qualidade de código:"
	@echo "  lint         - Executar linters (flake8, mypy)"
	@echo "  fmt          - Formatar código (black, isort)"
	@echo "  test         - Executar testes"
	@echo ""
	@echo "Banco de dados:"
	@echo "  migrate      - Executar migrações Alembic"
	@echo "  db-reset     - Resetar banco de dados"
	@echo ""
	@echo "Ingestão de dados:"
	@echo "  ingest       - Ingerir dados (ANVISA, SIDER, DrugCentral)"
	@echo "  reindex      - Reindexar embeddings"
	@echo ""
	@echo "Manutenção:"
	@echo "  clean        - Limpar arquivos temporários"
	@echo "  backup       - Fazer backup do banco"
	@echo "  restore      - Restaurar backup do banco"

# Desenvolvimento
# SKILL: debugging-strategies
# FIX: Porta mudada 8000 → 9000 → 9001 (conflito)
dev: build up
	@echo "🚀 Ambiente de desenvolvimento iniciado!"
	@echo "📱 API: http://localhost:9001"
	@echo "📊 Docs: http://localhost:9001/docs"
	@echo "🔍 Health: http://localhost:9001/healthz"

build:
	@echo "🔨 Construindo imagens Docker..."
	docker-compose -f $(COMPOSE_FILE) build

up:
	@echo "⬆️  Subindo serviços..."
	docker-compose -f $(COMPOSE_FILE) up -d

down:
	@echo "⬇️  Parando serviços..."
	docker-compose -f $(COMPOSE_FILE) down

logs:
	@echo "📋 Exibindo logs..."
	docker-compose -f $(COMPOSE_FILE) logs -f

# Qualidade de código
lint:
	@echo "🔍 Executando linters..."
	@echo "Flake8..."
	flake8 backend/ --max-line-length=88 --ignore=E203,W503
	@echo "MyPy..."
	mypy backend/ --ignore-missing-imports
	@echo "✅ Linting concluído!"

fmt:
	@echo "🎨 Formatando código..."
	@echo "Black..."
	black backend/ --line-length=88
	@echo "isort..."
	isort backend/ --profile=black
	@echo "✅ Formatação concluída!"

test:
	@echo "🧪 Executando testes..."
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=html
	@echo "✅ Testes concluídos!"

# Banco de dados
migrate:
	@echo "🗄️  Executando migrações..."
	cd backend && alembic upgrade head

db-reset:
	@echo "⚠️  Resetando banco de dados..."
	docker-compose -f $(COMPOSE_FILE) down -v
	docker-compose -f $(COMPOSE_FILE) up -d db
	@echo "⏳ Aguardando banco inicializar..."
	sleep 10
	@echo "✅ Banco resetado!"

# Ingestão de dados
ingest:
	@echo "📥 Iniciando ingestão de dados..."
	@echo "ANVISA..."
	python infra/scripts/ingest_anvisa.py --query "dipirona" --max 20
	@echo "SIDER..."
	python infra/scripts/ingest_sider.py
	@echo "DrugCentral..."
	python infra/scripts/ingest_drugcentral.py
	@echo "✅ Ingestão concluída!"

reindex:
	@echo "🔍 Reindexando embeddings..."
	python infra/scripts/reindex_embeddings.py
	@echo "✅ Reindexação concluída!"

# Manutenção
clean:
	@echo "🧹 Limpando arquivos temporários..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name ".coverage" -delete
	rm -rf backend/app/__pycache__
	rm -rf backend/app/*/__pycache__
	@echo "✅ Limpeza concluída!"

backup:
	@echo "💾 Fazendo backup do banco..."
	docker exec medsafe_db pg_dump -U medsafe medsafe > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup concluído!"

restore:
	@echo "📥 Restaurando backup..."
	@read -p "Digite o nome do arquivo de backup: " backup_file; \
	docker exec -i medsafe_db psql -U medsafe medsafe < $$backup_file
	@echo "✅ Restauração concluída!"

# Comandos específicos
setup-ollama:
	@echo "🤖 Configurando Ollama..."
	./setup_ollama.py

start:
	@echo "🚀 Iniciando MedSafe..."
	./start.sh

start-hf:
	@echo "🚀 Iniciando MedSafe com Hugging Face..."
	./start_hf.sh

# Comandos de produção
prod-up:
	@echo "🚀 Subindo ambiente de produção..."
	docker-compose -f $(COMPOSE_FILE) --profile production up -d

prod-down:
	@echo "⬇️  Parando ambiente de produção..."
	docker-compose -f $(COMPOSE_FILE) --profile production down

# Comandos de monitoramento
monitoring:
	@echo "📊 Iniciando serviços de monitoramento..."
	docker-compose -f $(COMPOSE_FILE) --profile monitoring up -d
	@echo "📈 Prometheus: http://localhost:9090"
	@echo "📊 Grafana: http://localhost:3001 (admin/admin)"

# Comandos de cache
cache:
	@echo "⚡ Iniciando serviços de cache..."
	docker-compose -f $(COMPOSE_FILE) --profile cache up -d

# Comandos de frontend
web:
	@echo "🌐 Iniciando frontend Next.js..."
	docker-compose -f $(COMPOSE_FILE) --profile web up -d
	@echo "🌐 Frontend: http://localhost:3000"

# Comandos de desenvolvimento rápido
dev-fast:
	@echo "⚡ Iniciando desenvolvimento rápido..."
	docker-compose -f $(COMPOSE_FILE) up -d db ollama
	@echo "⏳ Aguardando serviços..."
	sleep 15
	# SKILL: debugging-strategies
	# FIX: Porta mudada para 9001 (modo desenvolvimento local, não Docker)
	cd backend/app && python -m uvicorn main:app --host 0.0.0.0 --port 9001 --reload

# Comandos de saúde
health:
	@echo "🏥 Verificando saúde dos serviços..."
	@echo "API..."
	# SKILL: debugging-strategies
	# FIX: Porta mudada para 9001
	curl -f http://localhost:9001/healthz || echo "❌ API não está saudável"
	@echo "Banco..."
	docker exec medsafe_db pg_isready -U medsafe || echo "❌ Banco não está saudável"
	@echo "Ollama..."
	curl -f http://localhost:11434/api/tags || echo "❌ Ollama não está saudável"

# Comandos de logs específicos
logs-api:
	@echo "📋 Logs da API..."
	docker-compose -f $(COMPOSE_FILE) logs -f api

logs-db:
	@echo "📋 Logs do banco..."
	docker-compose -f $(COMPOSE_FILE) logs -f db

logs-ollama:
	@echo "📋 Logs do Ollama..."
	docker-compose -f $(COMPOSE_FILE) logs -f ollama

# Comandos de desenvolvimento local
local-dev:
	@echo "💻 Configurando desenvolvimento local..."
	@echo "Instalando dependências..."
	$(PIP) install -r requirements.txt
	@echo "Configurando banco local..."
	@echo "⚠️  Certifique-se de ter PostgreSQL + pgvector instalado localmente"
	@echo "✅ Desenvolvimento local configurado!"
	@echo "Execute: cd backend/app && python -m uvicorn main:app --reload"

# Comandos de teste específicos
test-unit:
	@echo "🧪 Executando testes unitários..."
	cd backend && python -m pytest tests/ -v --ignore=tests/e2e

test-integration:
	@echo "🧪 Executando testes de integração..."
	cd backend && python -m pytest tests/test_integration.py -v

test-e2e:
	@echo "🧪 Executando testes end-to-end..."
	@echo "📋 Iniciando serviços..."
	make up
	@echo "⏳ Aguardando serviços..."
	sleep 30
	cd tests && python -m pytest e2e/ -v --browser chromium || true
	@echo "✅ Testes E2E concluídos!"

test-coverage:
	@echo "📊 Executando testes com cobertura..."
	cd backend && python -m pytest tests/ -v \
		--cov=app \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		--ignore=tests/e2e
	@echo "✅ Relatório de cobertura disponível em backend/htmlcov/"

test-security:
	@echo "🔒 Executando testes de segurança..."
	bandit -r backend/app -f txt --severity-level medium
	safety check -r requirements.txt || true
	@echo "✅ Testes de segurança concluídos!"

# Comandos de documentação
docs:
	@echo "📚 Gerando documentação..."
	cd backend && python -m uvicorn main:app --reload &
	# SKILL: debugging-strategies
	# FIX: Porta mudada para 9001
	@echo "📖 Documentação disponível em: http://localhost:9001/docs"
	@echo "📖 ReDoc disponível em: http://localhost:9001/redoc"

# Comandos de deploy
deploy-staging:
	@echo "🚀 Deploy para staging..."
	@echo "⚠️  Implementar pipeline de deploy para staging"

deploy-production:
	@echo "🚀 Deploy para produção..."
	@echo "⚠️  Implementar pipeline de deploy para produção"

