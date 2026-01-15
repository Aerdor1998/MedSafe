#!/bin/bash

# ========================================
# MedSafe - Script de Status Docker
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

echo "========================================"
echo "📊 MedSafe - Status dos Serviços"
echo "========================================"
echo ""

# ========================================
# 1. Status dos Containers
# ========================================
echo -e "${BLUE}🐳 Containers Docker:${NC}"
echo ""

if docker ps -a | grep -q "medsafe"; then
    $DOCKER_COMPOSE ps
else
    echo -e "${YELLOW}⚠️  Nenhum container MedSafe encontrado${NC}"
    echo "   Execute: ./docker-start.sh"
fi

echo ""

# ========================================
# 2. Health Checks
# ========================================
echo -e "${BLUE}💚 Health Checks:${NC}"
echo ""

# Função para verificar serviço
check_service() {
    local SERVICE_NAME=$1
    local CHECK_CMD=$2

    echo -n "   $SERVICE_NAME: "

    if eval "$CHECK_CMD" &> /dev/null; then
        echo -e "${GREEN}✅ Healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ Unhealthy${NC}"
        return 1
    fi
}

# Verificar PostgreSQL
check_service "PostgreSQL (5432)" "docker exec medsafe_db pg_isready -U medsafe"

# Verificar Ollama
check_service "Ollama (11434)" "curl -f http://localhost:11434/api/tags"

# Verificar API
check_service "API (9000)" "curl -f http://localhost:9000/healthz"

echo ""

# ========================================
# 3. Informações da API
# ========================================
if curl -f http://localhost:9000/healthz &> /dev/null; then
    echo -e "${BLUE}🌐 API MedSafe:${NC}"
    echo ""

    API_HEALTH=$(curl -s http://localhost:9000/healthz | python3 -m json.tool 2>/dev/null || echo "{}")

    if [ ! -z "$API_HEALTH" ] && [ "$API_HEALTH" != "{}" ]; then
        echo "$API_HEALTH" | grep -E "status|version|database|ollama" | sed 's/^/   /'
    fi

    echo ""
fi

# ========================================
# 4. Recursos dos Containers
# ========================================
echo -e "${BLUE}💾 Uso de Recursos:${NC}"
echo ""

if docker ps | grep -q "medsafe"; then
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
        $(docker ps --filter "name=medsafe" -q) 2>/dev/null || echo "   Não foi possível obter métricas"
fi

echo ""

# ========================================
# 5. Volumes
# ========================================
echo -e "${BLUE}📦 Volumes Docker:${NC}"
echo ""

if docker volume ls | grep -q "medsafe"; then
    docker volume ls --filter "name=medsafe" --format "table {{.Name}}\t{{.Driver}}\t{{.Mountpoint}}"
else
    echo -e "${YELLOW}   Nenhum volume MedSafe encontrado${NC}"
fi

echo ""

# ========================================
# 6. Logs Recentes (últimas 5 linhas)
# ========================================
echo -e "${BLUE}📝 Logs Recentes (API):${NC}"
echo ""

if docker ps | grep -q "medsafe_api"; then
    docker logs --tail 5 medsafe_api 2>/dev/null | sed 's/^/   /' || echo "   Não foi possível obter logs"
else
    echo -e "${YELLOW}   Container API não está rodando${NC}"
fi

echo ""

# ========================================
# URLs e Comandos Úteis
# ========================================
echo "========================================"
echo -e "${BLUE}📍 URLs Disponíveis:${NC}"
echo ""

if curl -f http://localhost:9000/healthz &> /dev/null; then
    echo -e "   🌐 Interface Web:    ${GREEN}http://localhost:9000${NC}"
    echo -e "   📚 API Docs:         ${GREEN}http://localhost:9000/docs${NC}"
    echo -e "   📖 ReDoc:            ${GREEN}http://localhost:9000/redoc${NC}"
    echo -e "   💚 Health Check:     ${GREEN}http://localhost:9000/healthz${NC}"
else
    echo -e "   ${RED}❌ API não está acessível${NC}"
fi

echo ""
echo "📝 Comandos Úteis:"
echo "   Ver logs (tempo real):    docker-compose logs -f api"
echo "   Reiniciar API:            docker-compose restart api"
echo "   Parar tudo:               docker-compose down"
echo "   Executar comando no DB:   docker exec -it medsafe_db psql -U medsafe -d medsafe"
echo "   Shell no container API:   docker exec -it medsafe_api /bin/bash"
echo ""
echo "========================================"
echo ""
