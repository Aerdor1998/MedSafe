#!/bin/bash

# ========================================
# MedSafe - Troubleshooting Docker
# ========================================

# SKILL: debugging-strategies
# Script para diagnosticar problemas com Docker e Docker Hub

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "🔍 MedSafe - Diagnóstico Docker"
echo "========================================"
echo ""

# ========================================
# 1. Verificar Docker Daemon
# ========================================
echo -e "${BLUE}1. Docker Daemon:${NC}"

if docker info &> /dev/null; then
    echo -e "   ${GREEN}✅ Docker daemon está rodando${NC}"

    # Mostrar informações
    DOCKER_VERSION=$(docker version --format '{{.Server.Version}}')
    echo "   Versão: $DOCKER_VERSION"
else
    echo -e "   ${RED}❌ Docker daemon NÃO está rodando${NC}"
    echo ""
    echo "Soluções:"
    echo "  - Linux: sudo systemctl start docker"
    echo "  - Mac/Windows: Inicie o Docker Desktop"
    exit 1
fi

echo ""

# ========================================
# 2. Verificar Conectividade Internet
# ========================================
echo -e "${BLUE}2. Conectividade Internet:${NC}"

if ping -c 1 8.8.8.8 &> /dev/null; then
    echo -e "   ${GREEN}✅ Internet funcionando${NC}"
else
    echo -e "   ${RED}❌ Sem conexão com internet${NC}"
    echo "   Verifique sua conexão de rede"
    exit 1
fi

echo ""

# ========================================
# 3. Verificar DNS
# ========================================
echo -e "${BLUE}3. Resolução DNS:${NC}"

if nslookup registry-1.docker.io &> /dev/null || host registry-1.docker.io &> /dev/null; then
    echo -e "   ${GREEN}✅ DNS resolvendo registry-1.docker.io${NC}"
else
    echo -e "   ${RED}❌ Falha ao resolver registry-1.docker.io${NC}"
    echo ""
    echo "Soluções:"
    echo "  1. Adicionar DNS público ao Docker:"
    echo "     sudo nano /etc/docker/daemon.json"
    echo "     {"
    echo '       "dns": ["8.8.8.8", "8.8.4.4"]'
    echo "     }"
    echo "     sudo systemctl restart docker"
    echo ""
    echo "  2. Verificar /etc/resolv.conf"
fi

echo ""

# ========================================
# 4. Verificar Conectividade Docker Hub
# ========================================
echo -e "${BLUE}4. Docker Hub (registry-1.docker.io):${NC}"

if curl -m 10 -s https://registry-1.docker.io/v2/ &> /dev/null; then
    echo -e "   ${GREEN}✅ Docker Hub acessível${NC}"
else
    echo -e "   ${YELLOW}⚠️  Docker Hub com problemas de conectividade${NC}"
    echo ""
    echo "Possíveis causas:"
    echo "  - Firewall bloqueando porta 443"
    echo "  - Proxy corporativo"
    echo "  - Rate limit do Docker Hub"
    echo "  - Docker Hub temporariamente indisponível"
fi

echo ""

# ========================================
# 5. Verificar Rate Limit Docker Hub
# ========================================
echo -e "${BLUE}5. Rate Limit Docker Hub:${NC}"

TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:ratelimitpreview/test:pull" 2>/dev/null | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ ! -z "$TOKEN" ]; then
    RATE_LIMIT=$(curl -s --head -H "Authorization: Bearer $TOKEN" https://registry-1.docker.io/v2/ratelimitpreview/test/manifests/latest 2>/dev/null | grep -i ratelimit)

    if [ ! -z "$RATE_LIMIT" ]; then
        echo "$RATE_LIMIT" | while read line; do
            echo "   $line"
        done
    else
        echo -e "   ${YELLOW}⚠️  Não foi possível verificar rate limit${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Não foi possível obter token${NC}"
fi

echo ""

# ========================================
# 6. Verificar Imagens Locais
# ========================================
echo -e "${BLUE}6. Imagens Locais (Cache):${NC}"

if docker images python:3.10-slim --format "{{.Repository}}:{{.Tag}}" | grep -q "python:3.10-slim"; then
    echo -e "   ${GREEN}✅ python:3.10-slim já existe localmente${NC}"

    # Mostrar detalhes
    SIZE=$(docker images python:3.10-slim --format "{{.Size}}")
    CREATED=$(docker images python:3.10-slim --format "{{.CreatedSince}}")
    echo "   Tamanho: $SIZE"
    echo "   Criada: $CREATED"
else
    echo -e "   ${YELLOW}⚠️  python:3.10-slim não está no cache local${NC}"
    echo "   Será necessário baixar (~120MB)"
fi

echo ""

# ========================================
# 7. Testar Pull de Imagem
# ========================================
echo -e "${BLUE}7. Teste de Pull:${NC}"
echo "   Tentando baixar python:3.10-slim..."

if timeout 60 docker pull python:3.10-slim &> /dev/null; then
    echo -e "   ${GREEN}✅ Pull bem-sucedido!${NC}"
else
    echo -e "   ${RED}❌ Falha no pull${NC}"
    echo ""
    echo "Soluções:"
    echo "  1. Fazer login no Docker Hub:"
    echo "     docker login"
    echo ""
    echo "  2. Configurar DNS no Docker:"
    echo "     sudo nano /etc/docker/daemon.json"
    echo "     {"
    echo '       "dns": ["8.8.8.8", "1.1.1.1"]'
    echo "     }"
    echo "     sudo systemctl restart docker"
    echo ""
    echo "  3. Usar mirror do Docker Hub:"
    echo "     {"
    echo '       "registry-mirrors": ["https://mirror.gcr.io"]'
    echo "     }"
    echo ""
    echo "  4. Aguardar e tentar novamente (pode ser temporário)"
fi

echo ""

# ========================================
# 8. Verificar Daemon.json
# ========================================
echo -e "${BLUE}8. Configuração Docker (/etc/docker/daemon.json):${NC}"

if [ -f "/etc/docker/daemon.json" ]; then
    echo -e "   ${GREEN}✅ Arquivo existe${NC}"
    echo "   Conteúdo:"
    cat /etc/docker/daemon.json | sed 's/^/     /'
else
    echo -e "   ${YELLOW}⚠️  Arquivo não existe (usando padrões)${NC}"
fi

echo ""

# ========================================
# Resumo e Recomendações
# ========================================
echo "========================================"
echo -e "${BLUE}📋 Resumo:${NC}"
echo "========================================"
echo ""

# Verificar se tudo está OK
ALL_OK=true

if ! docker info &> /dev/null; then
    ALL_OK=false
    echo -e "${RED}❌ Docker daemon não está rodando${NC}"
fi

if ! ping -c 1 8.8.8.8 &> /dev/null; then
    ALL_OK=false
    echo -e "${RED}❌ Sem internet${NC}"
fi

if ! curl -m 10 -s https://registry-1.docker.io/v2/ &> /dev/null; then
    ALL_OK=false
    echo -e "${YELLOW}⚠️  Docker Hub com problemas${NC}"
fi

if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}✅ Tudo parece OK!${NC}"
    echo ""
    echo "Se ainda tiver problemas, tente:"
    echo "  1. Reiniciar Docker daemon"
    echo "  2. Fazer login: docker login"
    echo "  3. Usar VPN/proxy diferente"
else
    echo ""
    echo "Problemas detectados. Siga as soluções acima."
fi

echo ""
echo "========================================"
