#!/bin/bash

# ============================================================================
# MedSafe - Full Stack Stop Script
# ============================================================================
# Para todos os serviços: Core + Monitoring
#
# Usage:
#   ./scripts/medsafe-full-stop.sh              # Stop all
#   ./scripts/medsafe-full-stop.sh --clean      # Stop and remove volumes
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

CLEAN_VOLUMES=false

# Parse args
if [[ "$1" == "--clean" ]] || [[ "$1" == "-c" ]]; then
    CLEAN_VOLUMES=true
fi

# Detect docker compose
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo ""
echo -e "${BOLD}${CYAN}============================================${NC}"
echo -e "${BOLD}${CYAN}  MedSafe Full Stack Stop${NC}"
echo -e "${BOLD}${CYAN}============================================${NC}"
echo ""

# Stop monitoring stack
if [ -f "docker-compose.monitoring.yml" ]; then
    echo -e "${YELLOW}Stopping monitoring stack...${NC}"
    if [ "$CLEAN_VOLUMES" = true ]; then
        $DOCKER_COMPOSE -f docker-compose.monitoring.yml down -v 2>/dev/null || true
    else
        $DOCKER_COMPOSE -f docker-compose.monitoring.yml down 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ Monitoring stack stopped${NC}"
fi

# Stop core services
echo -e "${YELLOW}Stopping core services...${NC}"
if [ "$CLEAN_VOLUMES" = true ]; then
    $DOCKER_COMPOSE down -v --remove-orphans
    echo -e "${GREEN}✅ Core services stopped and volumes removed${NC}"
else
    $DOCKER_COMPOSE down --remove-orphans
    echo -e "${GREEN}✅ Core services stopped${NC}"
fi

echo ""
echo -e "${BOLD}${GREEN}All MedSafe services stopped!${NC}"
echo ""

if [ "$CLEAN_VOLUMES" = true ]; then
    echo -e "${YELLOW}Note: All data volumes were removed.${NC}"
    echo "      Database and monitoring data have been deleted."
fi

echo ""
