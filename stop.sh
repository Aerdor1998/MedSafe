#!/bin/bash

# ========================================
# MedSafe - Script de Parada
# ========================================

echo "========================================"
echo "🛑 MedSafe - Parando Aplicação"
echo "========================================"
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# ========================================
# 1. Parar FastAPI
# ========================================
echo "🔴 Parando servidor FastAPI..."
if pgrep -f "uvicorn.*backend.app.main" > /dev/null; then
    pkill -f "uvicorn.*backend.app.main"
    sleep 2
    echo -e "${GREEN}✅ FastAPI parado${NC}"
else
    echo "   FastAPI já estava parado"
fi

echo ""

# ========================================
# 2. Parar PostgreSQL
# ========================================
echo "🔴 Parando PostgreSQL..."
if docker ps | grep -q medsafe-postgres; then
    docker stop medsafe-postgres > /dev/null 2>&1
    echo -e "${GREEN}✅ PostgreSQL parado${NC}"
else
    echo "   PostgreSQL já estava parado"
fi

echo ""

# ========================================
# 3. Desativar ambiente virtual
# ========================================
if [ ! -z "$VIRTUAL_ENV" ]; then
    echo "🐍 Desativando ambiente virtual..."
    deactivate 2>/dev/null || true
    echo -e "${GREEN}✅ Ambiente virtual desativado${NC}"
fi

echo ""
echo "========================================"
echo "✅ MedSafe Parado"
echo "========================================"
echo ""
echo "Para iniciar novamente: ./start.sh"
echo ""

