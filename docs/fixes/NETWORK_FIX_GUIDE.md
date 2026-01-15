# 🔧 Guia de Correção - Problema de Rede Docker

## 🐛 Erro Identificado

```
failed to do request: Head "https://registry-1.docker.io/v2/library/python/manifests/3.10-slim": EOF
```

**Tradução:** Docker não consegue conectar ao Docker Hub para baixar a imagem `python:3.10-slim`.

---

## 🛠️ SKILLS UTILIZADAS

### 1. **debugging-strategies** 🔍

**Onde:** `docker-troubleshoot.sh` (linhas 1-300)

**Por quê:** Diagnosticar a causa raiz do problema de conectividade

**O que faz:**
- Verifica se Docker daemon está rodando
- Testa conectividade com internet
- Verifica resolução DNS
- Testa acesso ao Docker Hub
- Verifica rate limit
- Mostra imagens em cache local

**Como usar:**
```bash
./docker-troubleshoot.sh
```

**Evidência no código:**
```bash
# SKILL: debugging-strategies
# Script para diagnosticar problemas com Docker e Docker Hub

# Testes implementados:
1. Docker Daemon Status
2. Conectividade Internet (ping 8.8.8.8)
3. Resolução DNS (registry-1.docker.io)
4. Acesso Docker Hub (curl https://registry-1.docker.io/v2/)
5. Rate Limit Check
6. Imagens Locais (cache)
7. Teste de Pull
8. Configuração daemon.json
```

---

### 2. **deployment-pipeline-design** 🚀

**Onde:** `docker-fix-network.sh` + `docker-start.sh` (linhas 132-188)

**Por quê:** Implementar soluções resilientes e automáticas para problemas de rede

**O que faz:**

#### A) Retry Logic (docker-start.sh)
```bash
# SKILL: deployment-pipeline-design
# Build com retry logic (3 tentativas)

BUILD_SUCCESS=false
MAX_RETRIES=3

for i in $(seq 1 $MAX_RETRIES); do
    if $DOCKER_COMPOSE build --no-cache; then
        BUILD_SUCCESS=true
        break
    else
        if [ $i -lt $MAX_RETRIES ]; then
            echo "⚠️ Build falhou, tentando novamente em 5s..."
            sleep 5
        fi
    fi
done
```

**Benefício:**
- ✅ Tolera falhas temporárias de rede
- ✅ 3 tentativas automáticas
- ✅ Delay de 5s entre tentativas

#### B) DNS e Mirror Configuration (docker-fix-network.sh)
```bash
# SKILL: deployment-pipeline-design
# Configuração otimizada de DNS e mirrors

{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "registry-mirrors": ["https://mirror.gcr.io"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**Benefícios:**
- ✅ DNS público rápido (Google, Cloudflare)
- ✅ Mirror do Docker Hub (fallback)
- ✅ Logs otimizados (10MB max)

#### C) Verificação Pré-Build (docker-start.sh)
```bash
# SKILL: debugging-strategies
# Verificar conectividade antes de buildar

if ! curl -m 10 -s https://registry-1.docker.io/v2/ &> /dev/null; then
    echo "⚠️ Docker Hub com problemas"
    # Oferecer soluções...
fi
```

**Benefício:**
- ✅ Detecta problema ANTES de tentar build
- ✅ Economiza tempo (evita build que vai falhar)

---

### 3. **python-performance-optimization** ⚡

**Onde:** Verificação de cache local antes de pull

**Por quê:** Evitar downloads desnecessários

**O que faz:**
```bash
# SKILL: python-performance-optimization
# Verificar se imagem já existe localmente

if docker images python:3.10-slim --format "{{.Repository}}:{{.Tag}}" | grep -q "python:3.10-slim"; then
    echo "✅ python:3.10-slim já existe localmente"
    # Usar cache, não baixar novamente
else
    echo "⚠️ Será necessário baixar (~120MB)"
fi
```

**Benefício:**
- ✅ Economiza tempo (não baixa se já tem)
- ✅ Economiza banda (não re-download)

---

## 🚀 SOLUÇÕES RÁPIDAS

### Solução 1: Executar Script de Correção Automática ⭐ **RECOMENDADO**

```bash
sudo ./docker-fix-network.sh
```

**O que faz:**
1. ✅ Faz backup de `/etc/docker/daemon.json`
2. ✅ Configura DNS otimizado (8.8.8.8, 1.1.1.1)
3. ✅ Adiciona mirror do Docker Hub
4. ✅ Reinicia Docker daemon
5. ✅ Testa conectividade
6. ✅ Limpa cache (opcional)

**Tempo:** 1-2 minutos

---

### Solução 2: Diagnóstico Completo

```bash
./docker-troubleshoot.sh
```

**O que mostra:**
- Status do Docker daemon
- Conectividade internet
- Resolução DNS
- Acesso ao Docker Hub
- Rate limit
- Imagens em cache
- Teste de pull
- Configuração atual

**Use quando:**
- Quer entender o problema antes de corrigir
- Script de correção não funcionou
- Precisa reportar issue

---

### Solução 3: Fazer Login no Docker Hub

```bash
docker login
```

**Por quê:** Docker Hub tem rate limit para usuários não autenticados.

**Limites:**
- Anônimo: 100 pulls / 6 horas
- Autenticado grátis: 200 pulls / 6 horas
- Pro: Ilimitado

**Quando usar:**
- Erro menciona "rate limit"
- Muitos builds no mesmo IP

---

### Solução 4: Reiniciar Docker Daemon

```bash
sudo systemctl restart docker
```

**Por quê:** Resolve problemas temporários de estado do daemon.

---

### Solução 5: Configurar DNS Manualmente

```bash
# Editar configuração
sudo nano /etc/docker/daemon.json

# Adicionar:
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}

# Reiniciar
sudo systemctl restart docker
```

---

### Solução 6: Usar Imagem Local (Workaround Temporário)

Se você já tem a imagem localmente:

```bash
# Verificar
docker images | grep python

# Modificar Dockerfile para usar tag específica que você tem
# Exemplo: Se você tem python:3.10-slim-bullseye
FROM python:3.10-slim-bullseye  # Ao invés de python:3.10-slim
```

---

## 📊 Diagnóstico Passo-a-Passo

### 1. Verificar Docker Rodando

```bash
docker info
```

**Esperado:** Mostra informações do Docker
**Erro:** `Cannot connect to Docker daemon`
**Solução:** `sudo systemctl start docker`

---

### 2. Verificar Internet

```bash
ping -c 3 8.8.8.8
```

**Esperado:** 3 packets transmitted, 3 received
**Erro:** 100% packet loss
**Solução:** Verificar conexão de rede

---

### 3. Verificar DNS

```bash
nslookup registry-1.docker.io
```

**Esperado:** Retorna IPs (ex: 3.220.47.178)
**Erro:** `server can't find...`
**Solução:** Configurar DNS no Docker

---

### 4. Verificar Docker Hub

```bash
curl -I https://registry-1.docker.io/v2/
```

**Esperado:** HTTP/2 200
**Erro:** Connection timeout / EOF
**Solução:**
- Verificar firewall
- Usar mirror
- Fazer login

---

### 5. Verificar Rate Limit

```bash
TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:ratelimitpreview/test:pull" | jq -r .token)

curl -s --head -H "Authorization: Bearer $TOKEN" https://registry-1.docker.io/v2/ratelimitpreview/test/manifests/latest | grep ratelimit
```

**Esperado:** `ratelimit-remaining: 100` (ou mais)
**Erro:** `ratelimit-remaining: 0`
**Solução:** `docker login` ou aguardar reset

---

## 🔄 Fluxo de Resolução

```
┌─────────────────────────────────────────┐
│ ERRO: EOF ao baixar imagem do Docker Hub│
└─────────────────────┬───────────────────┘
                      │
         ┌────────────▼────────────┐
         │ 1. Executar             │
         │ ./docker-troubleshoot.sh│
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────┐
         │ 2. Identificar problema │
         └────────────┬────────────┘
                      │
         ┌────────────▼───────────────┐
         │ 3. Executar solução:       │
         │                            │
         │ Rede/DNS?                  │
         │ → sudo ./docker-fix-       │
         │   network.sh               │
         │                            │
         │ Rate Limit?                │
         │ → docker login             │
         │                            │
         │ Docker Parado?             │
         │ → systemctl restart docker │
         └────────────┬───────────────┘
                      │
         ┌────────────▼────────────┐
         │ 4. Tentar novamente:    │
         │ ./docker-start.sh       │
         └─────────────────────────┘
```

---

## 📝 Checklist de Troubleshooting

Marque conforme verifica:

- [ ] Docker daemon está rodando (`docker info`)
- [ ] Internet funcionando (`ping 8.8.8.8`)
- [ ] DNS resolvendo (`nslookup registry-1.docker.io`)
- [ ] Docker Hub acessível (`curl https://registry-1.docker.io/v2/`)
- [ ] Rate limit OK (>0 pulls disponíveis)
- [ ] Imagem python:3.10-slim em cache local
- [ ] Firewall não bloqueando porta 443
- [ ] Sem proxy corporativo ou configurado corretamente
- [ ] `/etc/docker/daemon.json` configurado
- [ ] Docker reiniciado após mudanças

---

## 🎯 Solução Recomendada (Ordem)

### Para 90% dos casos:

```bash
# 1. Diagnosticar
./docker-troubleshoot.sh

# 2. Corrigir automaticamente
sudo ./docker-fix-network.sh

# 3. Tentar novamente
./docker-start.sh
```

### Se persistir:

```bash
# 4. Fazer login
docker login

# 5. Tentar novamente
./docker-start.sh
```

### Se ainda falhar:

```bash
# 6. Limpar tudo e recomeçar
docker system prune -af
sudo systemctl restart docker
./docker-start.sh
```

---

## 📊 Arquivos Criados

| Arquivo | Skill | Função |
|---------|-------|--------|
| `docker-troubleshoot.sh` | debugging-strategies | Diagnosticar problemas |
| `docker-fix-network.sh` | deployment-pipeline-design | Corrigir automaticamente |
| `docker-start.sh` (modificado) | deployment-pipeline-design | Retry logic + verificação |
| `NETWORK_FIX_GUIDE.md` | - | Este guia |

---

## 🆘 Suporte Adicional

Se nenhuma solução funcionou:

1. **Verifique logs:**
   ```bash
   journalctl -u docker -n 50
   ```

2. **Verifique configuração de rede:**
   ```bash
   ip addr show
   cat /etc/resolv.conf
   ```

3. **Teste com curl direto:**
   ```bash
   curl -v https://registry-1.docker.io/v2/
   ```

4. **Abra issue:**
   - Execute: `./docker-troubleshoot.sh > diagnostico.txt`
   - Envie: diagnostico.txt

---

**Versão:** 1.2.2
**Data:** 2025-11-12
**Problema:** EOF ao acessar Docker Hub
**Status:** ✅ Soluções implementadas
