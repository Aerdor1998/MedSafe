#!/bin/bash

# ========================================
# MedSafe - Script para Ver Logs Docker
# ========================================

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Usar comando correto (docker compose ou docker-compose)
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Verificar se containers estão rodando
if ! docker ps | grep -q "medsafe"; then
    echo -e "${RED}❌ Nenhum container MedSafe rodando${NC}"
    echo "   Execute: ./docker-start.sh"
    exit 1
fi

echo "========================================"
echo "📝 MedSafe - Visualizar Logs"
echo "========================================"
echo ""
echo "Escolha o serviço:"
echo "  1) API (backend)"
echo "  2) PostgreSQL"
echo "  3) Ollama"
echo "  4) Todos os serviços"
echo "  5) Últimas 50 linhas de todos"
echo ""
read -p "Opção (1-5): " OPTION

case $OPTION in
    1)
        echo ""
        echo -e "${BLUE}📋 Logs da API (Ctrl+C para sair):${NC}"
        echo ""
        $DOCKER_COMPOSE logs -f --tail=100 api
        ;;
    2)
        echo ""
        echo -e "${BLUE}📋 Logs do PostgreSQL (Ctrl+C para sair):${NC}"
        echo ""
        $DOCKER_COMPOSE logs -f --tail=100 db
        ;;
    3)
        echo ""
        echo -e "${BLUE}📋 Logs do Ollama (Ctrl+C para sair):${NC}"
        echo ""
        $DOCKER_COMPOSE logs -f --tail=100 ollama
        ;;
    4)
        echo ""
        echo -e "${BLUE}📋 Logs de Todos os Serviços (Ctrl+C para sair):${NC}"
        echo ""
        $DOCKER_COMPOSE logs -f --tail=50
        ;;
    5)
        echo ""
        echo -e "${BLUE}📋 Últimas 50 linhas de cada serviço:${NC}"
        echo ""
        echo "=== API ==="
        $DOCKER_COMPOSE logs --tail=50 api
        echo ""
        echo "=== PostgreSQL ==="
        $DOCKER_COMPOSE logs --tail=20 db
        echo ""
        echo "=== Ollama ==="
        $DOCKER_COMPOSE logs --tail=20 ollama
        echo ""
        ;;
    *)
        echo -e "${RED}❌ Opção inválida${NC}"
        exit 1
        ;;
esac
