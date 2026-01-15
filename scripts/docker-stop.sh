#!/bin/bash

# ========================================
# MedSafe - Script para Parar Docker
# ========================================

set -e

echo "========================================"
echo "🛑 MedSafe - Parando Containers"
echo "========================================"
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# Verificar se há containers rodando
if ! docker ps | grep -q "medsafe"; then
    echo -e "${YELLOW}⚠️  Nenhum container MedSafe rodando${NC}"
    echo ""
    exit 0
fi

# Mostrar containers que serão parados
echo "📋 Containers que serão parados:"
docker ps --filter "name=medsafe" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Perguntar confirmação (opcional - comente se quiser parar sem perguntar)
read -p "Deseja parar todos os containers? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
    echo "❌ Operação cancelada"
    exit 0
fi

echo ""
echo "🛑 Parando containers..."

# Parar containers
$DOCKER_COMPOSE down

echo ""
echo -e "${GREEN}✅ Containers parados com sucesso!${NC}"
echo ""
echo "💡 Comandos úteis:"
echo "   Iniciar novamente:        ./docker-start.sh"
echo "   Parar e remover volumes:  docker-compose down -v"
echo "   Ver containers parados:   docker ps -a | grep medsafe"
echo ""
