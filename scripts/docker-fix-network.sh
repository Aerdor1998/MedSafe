#!/bin/bash

# ========================================
# MedSafe - Corrigir Problemas de Rede Docker
# ========================================

# SKILL: debugging-strategies + deployment-pipeline-design
# Script para corrigir problemas comuns de rede do Docker

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "🔧 MedSafe - Correção de Rede Docker"
echo "========================================"
echo ""

# Verificar se é root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Este script precisa de privilégios sudo${NC}"
    echo "   Executando com sudo..."
    sudo "$0" "$@"
    exit $?
fi

echo -e "${BLUE}SKILL: debugging-strategies${NC}"
echo "Diagnosticando e corrigindo problemas de rede..."
echo ""

# ========================================
# 1. Backup daemon.json existente
# ========================================
DAEMON_JSON="/etc/docker/daemon.json"

if [ -f "$DAEMON_JSON" ]; then
    echo "📋 Fazendo backup de daemon.json..."
    cp "$DAEMON_JSON" "${DAEMON_JSON}.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✅ Backup criado${NC}"
else
    echo "📋 Criando daemon.json..."
    mkdir -p /etc/docker
fi

echo ""

# ========================================
# 2. Configurar DNS e Mirrors
# ========================================
echo -e "${BLUE}SKILL: deployment-pipeline-design${NC}"
echo "Configurando DNS e mirrors otimizados..."

cat > "$DAEMON_JSON" << 'EOF'
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "registry-mirrors": [
    "https://mirror.gcr.io"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-address-pools": [
    {
      "base": "172.80.0.0/16",
      "size": 24
    }
  ]
}
EOF

echo -e "${GREEN}✅ Configuração atualizada${NC}"
echo ""

# Mostrar configuração
echo "📄 Nova configuração:"
cat "$DAEMON_JSON" | sed 's/^/   /'
echo ""

# ========================================
# 3. Reiniciar Docker
# ========================================
echo "🔄 Reiniciando Docker daemon..."

if systemctl restart docker; then
    echo -e "${GREEN}✅ Docker reiniciado${NC}"
else
    echo -e "${RED}❌ Erro ao reiniciar Docker${NC}"
    echo "   Tente: systemctl status docker"
    exit 1
fi

# Aguardar Docker ficar pronto
echo "⏳ Aguardando Docker ficar pronto..."
sleep 3

if docker info &> /dev/null; then
    echo -e "${GREEN}✅ Docker operacional${NC}"
else
    echo -e "${RED}❌ Docker não respondeu${NC}"
    exit 1
fi

echo ""

# ========================================
# 4. Testar Conectividade
# ========================================
echo "🔍 Testando conectividade..."

# Teste 1: DNS
echo -n "   DNS (8.8.8.8): "
if ping -c 1 8.8.8.8 &> /dev/null; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
fi

# Teste 2: Docker Hub
echo -n "   Docker Hub: "
if curl -m 10 -s https://registry-1.docker.io/v2/ &> /dev/null; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${YELLOW}⚠️${NC}"
fi

# Teste 3: Pull de imagem teste
echo -n "   Pull teste: "
if timeout 30 docker pull hello-world &> /dev/null; then
    echo -e "${GREEN}✅${NC}"
    docker rmi hello-world &> /dev/null || true
else
    echo -e "${RED}❌${NC}"
fi

echo ""

# ========================================
# 5. Limpar Cache (Opcional)
# ========================================
echo "🧹 Limpeza de cache..."

read -p "Deseja limpar build cache do Docker? (s/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[SsYy]$ ]]; then
    docker builder prune -af
    echo -e "${GREEN}✅ Cache limpo${NC}"
else
    echo "   Cache mantido"
fi

echo ""

# ========================================
# Resumo
# ========================================
echo "========================================"
echo -e "${GREEN}✅ Correção Concluída!${NC}"
echo "========================================"
echo ""
echo "Mudanças aplicadas:"
echo "  ✅ DNS configurado: 8.8.8.8, 8.8.4.4, 1.1.1.1"
echo "  ✅ Mirror adicionado: mirror.gcr.io"
echo "  ✅ Logs otimizados: 10MB max"
echo "  ✅ Docker reiniciado"
echo ""
echo "Próximos passos:"
echo "  1. Tente executar novamente: ./docker-start.sh"
echo "  2. Se persistir, faça login: docker login"
echo "  3. Verifique firewall/proxy corporativo"
echo ""
echo "Backup salvo em: ${DAEMON_JSON}.backup.*"
echo "========================================"
echo ""
