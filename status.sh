#!/bin/bash

# ========================================
# MedSafe - Verificação de Status
# ========================================

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "📊 MedSafe - Status do Sistema"
echo "========================================"
echo ""

# ========================================
# 1. PostgreSQL
# ========================================
echo "🐘 PostgreSQL:"
if docker ps | grep -q medsafe-postgres; then
    echo -e "   Status: ${GREEN}✅ Rodando${NC}"
    echo "   Porta:  5432"
    
    # Testar conexão
    if docker exec medsafe-postgres pg_isready -U medsafe > /dev/null 2>&1; then
        echo -e "   Conexão: ${GREEN}✅ OK${NC}"
    else
        echo -e "   Conexão: ${YELLOW}⚠️  Inicializando...${NC}"
    fi
    
    # Contar registros
    TRIAGES=$(docker exec medsafe-postgres psql -U medsafe -d medsafe -t -c "SELECT COUNT(*) FROM triage;" 2>/dev/null | tr -d ' ')
    REPORTS=$(docker exec medsafe-postgres psql -U medsafe -d medsafe -t -c "SELECT COUNT(*) FROM reports;" 2>/dev/null | tr -d ' ')
    echo "   Triagens: $TRIAGES"
    echo "   Relatórios: $REPORTS"
else
    echo -e "   Status: ${RED}❌ Parado${NC}"
fi

echo ""

# ========================================
# 2. FastAPI
# ========================================
echo "🚀 FastAPI:"
if pgrep -f "uvicorn.*backend.app.main" > /dev/null; then
    PID=$(pgrep -f "uvicorn.*backend.app.main")
    echo -e "   Status: ${GREEN}✅ Rodando${NC}"
    echo "   PID: $PID"
    echo "   Porta: 8000"
    
    # Testar health endpoint
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo -e "   Health: ${GREEN}✅ OK${NC}"
    else
        echo -e "   Health: ${RED}❌ Não responde${NC}"
    fi
else
    echo -e "   Status: ${RED}❌ Parado${NC}"
fi

echo ""

# ========================================
# 3. Frontend
# ========================================
echo "🌐 Frontend:"
if curl -s http://localhost:8000/ | grep -q "MedSafe" 2>/dev/null; then
    echo -e "   Status: ${GREEN}✅ Acessível${NC}"
    echo "   URL: http://localhost:8000"
else
    echo -e "   Status: ${RED}❌ Não acessível${NC}"
fi

echo ""

# ========================================
# 4. API Docs
# ========================================
echo "📚 API Documentation:"
if curl -s http://localhost:8000/docs | grep -q "swagger" 2>/dev/null; then
    echo -e "   Status: ${GREEN}✅ Disponível${NC}"
    echo "   URL: http://localhost:8000/docs"
else
    echo -e "   Status: ${RED}❌ Não disponível${NC}"
fi

echo ""

# ========================================
# 5. Portas em Uso
# ========================================
echo "🔌 Portas em Uso:"
if command -v lsof > /dev/null 2>&1; then
    if lsof -ti:5432 > /dev/null 2>&1; then
        echo -e "   5432 (PostgreSQL): ${GREEN}✅ Em uso${NC}"
    else
        echo -e "   5432 (PostgreSQL): ${RED}❌ Livre${NC}"
    fi
    
    if lsof -ti:8000 > /dev/null 2>&1; then
        echo -e "   8000 (FastAPI): ${GREEN}✅ Em uso${NC}"
    else
        echo -e "   8000 (FastAPI): ${RED}❌ Livre${NC}"
    fi
else
    echo "   lsof não disponível para verificar portas"
fi

echo ""

# ========================================
# 6. Disco
# ========================================
echo "💾 Uso de Disco:"
if command -v docker > /dev/null 2>&1; then
    VOLUME_SIZE=$(docker volume inspect medsafe_pgdata --format '{{ .Mountpoint }}' 2>/dev/null | xargs du -sh 2>/dev/null | cut -f1 || echo "N/A")
    echo "   Volume PostgreSQL: $VOLUME_SIZE"
fi

LOG_SIZE=$(du -sh /tmp/medsafe.log 2>/dev/null | cut -f1 || echo "0")
echo "   Logs: $LOG_SIZE"

echo ""

# ========================================
# 7. Últimas Linhas do Log
# ========================================
echo "📝 Últimas 5 linhas do log:"
if [ -f /tmp/medsafe.log ]; then
    tail -5 /tmp/medsafe.log | sed 's/^/   /'
else
    echo "   Nenhum log disponível"
fi

echo ""
echo "========================================"
echo "Para ver logs completos: tail -f /tmp/medsafe.log"
echo "========================================"

