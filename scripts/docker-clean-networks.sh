#!/bin/bash

# ========================================
# MedSafe - Limpeza de Redes Docker
# ========================================

# SKILL: python-performance-optimization
# Remove redes órfãs e não utilizadas para liberar recursos

# SKILL: debugging-strategies
# Previne conflitos de subnet ao limpar redes antigas

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "🧹 MedSafe - Limpeza de Redes Docker"
echo "========================================"
echo ""

# ========================================
# 1. Listar Redes Atuais
# ========================================
echo -e "${BLUE}📋 Redes Docker Atuais:${NC}"
echo ""

docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" | grep -v "NETWORK" | while read line; do
    echo "   $line"
done

echo ""

# ========================================
# 2. Verificar Redes Órfãs
# ========================================
echo -e "${BLUE}🔍 Verificando redes órfãs (sem containers)...${NC}"
echo ""

ORPHAN_NETWORKS=$(docker network ls --filter "dangling=true" -q)

if [ -z "$ORPHAN_NETWORKS" ]; then
    echo -e "   ${GREEN}✅ Nenhuma rede órfã encontrada${NC}"
else
    echo -e "   ${YELLOW}⚠️  Redes órfãs encontradas:${NC}"

    docker network ls --filter "dangling=true" --format "   - {{.Name}} ({{.ID}})"

    echo ""
    read -p "Deseja remover redes órfãs? (s/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[SsYy]$ ]]; then
        docker network prune -f
        echo -e "   ${GREEN}✅ Redes órfãs removidas${NC}"
    else
        echo "   Redes mantidas"
    fi
fi

echo ""

# ========================================
# 3. Verificar Conflitos de Subnet
# ========================================
echo -e "${BLUE}🔍 Mapeando subnets em uso:${NC}"
echo ""

# SKILL: debugging-strategies
# Identifica todas as subnets para prevenir conflitos

echo "Subnet              Rede"
echo "----------------    -------------------------"

for net in $(docker network ls --format "{{.Name}}" | grep -v "bridge\|host\|none"); do
    SUBNET=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "N/A")

    if [ "$SUBNET" != "N/A" ] && [ ! -z "$SUBNET" ]; then
        printf "%-18s  %s\n" "$SUBNET" "$net"
    fi
done

echo ""

# ========================================
# 4. Verificar Conflito com MedSafe
# ========================================
echo -e "${BLUE}🎯 Verificando conflito com MedSafe (172.22.0.0/16):${NC}"
echo ""

MEDSAFE_SUBNET="172.22.0.0/16"
CONFLICT=false

for net in $(docker network ls --format "{{.Name}}" | grep -v "medsafe"); do
    SUBNET=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "")

    if [ "$SUBNET" = "$MEDSAFE_SUBNET" ]; then
        CONFLICT=true
        echo -e "   ${RED}❌ CONFLITO: Rede '$net' já usa $MEDSAFE_SUBNET${NC}"
        echo ""
        echo "   Soluções:"
        echo "     1. Remover rede: docker network rm $net"
        echo "     2. Mudar subnet do MedSafe em docker-compose.yml"
        echo ""
    fi
done

if [ "$CONFLICT" = false ]; then
    echo -e "   ${GREEN}✅ Nenhum conflito encontrado para 172.22.0.0/16${NC}"
fi

echo ""

# ========================================
# 5. Remover Rede MedSafe Antiga (se existir)
# ========================================
echo -e "${BLUE}🗑️  Verificando rede MedSafe antiga:${NC}"
echo ""

if docker network ls | grep -q "medsafe"; then
    echo -e "   ${YELLOW}⚠️  Redes MedSafe encontradas:${NC}"

    docker network ls | grep "medsafe" | awk '{print "     - " $2}'

    echo ""
    read -p "Deseja remover redes MedSafe antigas? (s/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[SsYy]$ ]]; then
        # SKILL: python-performance-optimization
        # Remove apenas redes não utilizadas (sem containers ativos)

        for net in $(docker network ls --format "{{.Name}}" | grep "medsafe"); do
            # Verificar se tem containers conectados
            CONTAINERS=$(docker network inspect "$net" --format '{{len .Containers}}' 2>/dev/null || echo "0")

            if [ "$CONTAINERS" = "0" ]; then
                echo "   Removendo: $net"
                docker network rm "$net" 2>/dev/null || echo "     Falhou (pode estar em uso)"
            else
                echo "   Pulando: $net (tem $CONTAINERS containers)"
            fi
        done

        echo -e "   ${GREEN}✅ Limpeza concluída${NC}"
    else
        echo "   Redes mantidas"
    fi
else
    echo -e "   ${GREEN}✅ Nenhuma rede MedSafe antiga encontrada${NC}"
fi

echo ""

# ========================================
# 6. Resumo Final
# ========================================
echo "========================================"
echo -e "${BLUE}📊 Resumo:${NC}"
echo "========================================"
echo ""

TOTAL_NETWORKS=$(docker network ls --format "{{.Name}}" | wc -l)
ORPHAN_COUNT=$(docker network ls --filter "dangling=true" -q | wc -l)

echo "Total de redes Docker: $TOTAL_NETWORKS"
echo "Redes órfãs restantes: $ORPHAN_COUNT"
echo ""

if [ "$CONFLICT" = true ]; then
    echo -e "${RED}⚠️  Atenção: Conflitos de subnet detectados!${NC}"
    echo "   Resolva antes de executar docker-start.sh"
else
    echo -e "${GREEN}✅ Nenhum conflito de subnet${NC}"
    echo "   Pronto para executar: ./docker-start.sh"
fi

echo ""
echo "========================================"
