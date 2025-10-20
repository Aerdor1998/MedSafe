#!/bin/bash

# ========================================
# MedSafe - Script de Inicialização
# ========================================

set -e  # Parar em caso de erro

echo "========================================"
echo "🏥 MedSafe - Iniciando Aplicação"
echo "========================================"
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ========================================
# 1. Verificar e Iniciar PostgreSQL
# ========================================
echo "📊 Passo 1/3: Verificando PostgreSQL..."

if docker ps | grep -q medsafe-postgres; then
    echo -e "${GREEN}✅ PostgreSQL já está rodando${NC}"
else
    echo "   Iniciando container PostgreSQL..."
    docker start medsafe-postgres > /dev/null 2>&1 || {
        echo -e "${RED}❌ Erro ao iniciar PostgreSQL${NC}"
        echo "   Tente: docker start medsafe-postgres"
        exit 1
    }
    echo -e "${GREEN}✅ PostgreSQL iniciado${NC}"
    echo "   Aguardando inicialização..."
    sleep 5
fi

# Verificar conexão
docker exec medsafe-postgres pg_isready -U medsafe > /dev/null 2>&1 || {
    echo -e "${YELLOW}⚠️  PostgreSQL ainda inicializando, aguardando...${NC}"
    sleep 3
}

echo ""

# ========================================
# 2. Ativar Ambiente Virtual
# ========================================
echo "🐍 Passo 2/3: Configurando ambiente Python..."

if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Ambiente virtual não encontrado${NC}"
    echo "   Criando ambiente virtual..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Verificar se pip funciona
if ! python -m pip --version > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Atualizando pip...${NC}"
    python -m ensurepip --upgrade > /dev/null 2>&1
fi

echo -e "${GREEN}✅ Ambiente Python pronto${NC}"
echo ""

# ========================================
# 3. Iniciar Servidor FastAPI
# ========================================
echo "🚀 Passo 3/3: Iniciando servidor FastAPI..."

# Verificar se já está rodando
if pgrep -f "uvicorn.*backend.app.main" > /dev/null; then
    echo -e "${YELLOW}⚠️  Servidor já está rodando. Parando primeiro...${NC}"
    pkill -f "uvicorn.*backend.app.main"
    sleep 2
fi

# Limpar log antigo
rm -f /tmp/medsafe.log

# Iniciar servidor em background
nohup python -m uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > /tmp/medsafe.log 2>&1 &

SERVER_PID=$!
echo "   Servidor iniciando (PID: $SERVER_PID)..."
echo "   Aguardando inicialização..."

# Aguardar servidor ficar pronto
MAX_WAIT=15
COUNTER=0
while [ $COUNTER -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Servidor FastAPI pronto!${NC}"
        break
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
    echo -n "."
done

echo ""

if [ $COUNTER -eq $MAX_WAIT ]; then
    echo -e "${RED}❌ Timeout aguardando servidor${NC}"
    echo "   Verifique os logs: tail -f /tmp/medsafe.log"
    exit 1
fi

echo ""

# ========================================
# Status Final
# ========================================
echo "========================================"
echo "✅ MedSafe Iniciado com Sucesso!"
echo "========================================"
echo ""
echo "📍 URLs Disponíveis:"
echo "   🌐 Interface Web:    http://localhost:8000"
echo "   📚 API Docs:         http://localhost:8000/docs"
echo "   📖 ReDoc:            http://localhost:8000/redoc"
echo ""
echo "📊 Status dos Serviços:"
if docker ps | grep -q medsafe-postgres; then
    echo -e "   ${GREEN}✅ PostgreSQL: Rodando (porta 5432)${NC}"
else
    echo -e "   ${RED}❌ PostgreSQL: Parado${NC}"
fi

if pgrep -f "uvicorn.*backend.app.main" > /dev/null; then
    echo -e "   ${GREEN}✅ FastAPI: Rodando (porta 8000)${NC}"
else
    echo -e "   ${RED}❌ FastAPI: Parado${NC}"
fi

echo ""
echo "📝 Comandos Úteis:"
echo "   Ver logs:     tail -f /tmp/medsafe.log"
echo "   Parar tudo:   ./stop.sh"
echo "   Status:       ./status.sh"
echo ""
echo "🎉 Pronto para usar!"
echo "========================================"
