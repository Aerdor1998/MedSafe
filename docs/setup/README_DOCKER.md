# 🐳 MedSafe - Guia de Uso com Docker

## 📋 Índice

- [Pré-requisitos](#pré-requisitos)
- [Quick Start](#quick-start)
- [Scripts Disponíveis](#scripts-disponíveis)
- [Arquitetura Docker](#arquitetura-docker)
- [Comandos Úteis](#comandos-úteis)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Pré-requisitos

### 1. Docker e Docker Compose

**Linux (Ubuntu/Debian):**
```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

**macOS:**
```bash
# Instalar Docker Desktop
brew install --cask docker

# Ou baixar em: https://www.docker.com/products/docker-desktop
```

**Windows:**
- Baixe e instale [Docker Desktop](https://www.docker.com/products/docker-desktop)

### 2. Verificar Instalação

```bash
docker --version
# Docker version 24.0.0+

docker-compose --version
# Docker Compose version v2.20.0+
```

---

## 🚀 Quick Start

### 1. Iniciar Aplicação (Primeira Vez)

```bash
# Clonar repositório (se ainda não tiver)
cd /home/lucasmsilva/Documentos/Cursor/MedSafe

# Iniciar tudo com um comando
./docker-start.sh
```

**O que acontece:**
1. ✅ Verifica Docker e Docker Compose instalados
2. ✅ Cria arquivo `.env` automaticamente (se não existir)
3. ✅ Gera secrets seguros automaticamente
4. ✅ Constrói imagens Docker
5. ✅ Inicia PostgreSQL + Ollama + API
6. ✅ Aguarda todos os serviços ficarem prontos
7. ✅ Baixa modelos Ollama (qwen2.5:7b, qwen2.5vl:7b)
8. ✅ Mostra URLs e status

**Tempo estimado:** 5-15 minutos (primeira vez, download de modelos)

---

### 2. Acessar Aplicação

Após iniciar, acesse:

- **Interface Web:** http://localhost:9000
- **API Docs (Swagger):** http://localhost:9000/docs
- **ReDoc:** http://localhost:9000/redoc
- **Health Check:** http://localhost:9000/healthz

---

### 3. Parar Aplicação

```bash
./docker-stop.sh
```

---

## 📜 Scripts Disponíveis

### 1. `docker-start.sh` - Iniciar Aplicação

```bash
./docker-start.sh
```

**O que faz:**
- Verifica dependências (Docker, Docker Compose)
- Cria `.env` se não existir
- Gera secrets automaticamente
- Para containers antigos
- Constrói imagens
- Inicia todos os serviços
- Aguarda serviços ficarem prontos
- Baixa modelos Ollama (se necessário)
- Mostra status e URLs

**Uso:**
```bash
# Iniciar normalmente
./docker-start.sh

# Ver saída detalhada
./docker-start.sh 2>&1 | tee startup.log
```

---

### 2. `docker-stop.sh` - Parar Aplicação

```bash
./docker-stop.sh
```

**O que faz:**
- Lista containers que serão parados
- Pede confirmação
- Para todos os containers MedSafe
- Preserva volumes (dados não são perdidos)

**Opções:**
```bash
# Parar containers
./docker-stop.sh

# Parar E remover volumes (limpar tudo)
docker-compose down -v
```

---

### 3. `docker-status.sh` - Ver Status

```bash
./docker-status.sh
```

**O que mostra:**
- 🐳 Status dos containers
- 💚 Health checks (PostgreSQL, Ollama, API)
- 🌐 Informações da API (version, status)
- 💾 Uso de recursos (CPU, memória)
- 📦 Volumes Docker
- 📝 Logs recentes (últimas 5 linhas)
- 📍 URLs disponíveis
- 📝 Comandos úteis

**Exemplo de saída:**
```
📊 MedSafe - Status dos Serviços
========================================

🐳 Containers Docker:

NAME             STATUS          PORTS
medsafe_db       Up 2 minutes    0.0.0.0:5432->5432/tcp
medsafe_ollama   Up 2 minutes    0.0.0.0:11434->11434/tcp
medsafe_api      Up 2 minutes    0.0.0.0:9000->9000/tcp

💚 Health Checks:

   PostgreSQL (5432): ✅ Healthy
   Ollama (11434): ✅ Healthy
   API (9000): ✅ Healthy
```

---

### 4. `docker-logs.sh` - Ver Logs

```bash
./docker-logs.sh
```

**Menu interativo:**
```
📝 MedSafe - Visualizar Logs
========================================

Escolha o serviço:
  1) API (backend)
  2) PostgreSQL
  3) Ollama
  4) Todos os serviços
  5) Últimas 50 linhas de todos
```

**Uso:**
```bash
# Menu interativo
./docker-logs.sh

# Ou diretamente:
docker-compose logs -f api        # Logs da API em tempo real
docker-compose logs -f db         # Logs do PostgreSQL
docker-compose logs -f ollama     # Logs do Ollama
docker-compose logs -f            # Todos os logs
```

---

## 🏗️ Arquitetura Docker

### Containers

```
┌─────────────────────────────────────────────────────────────┐
│                        MedSafe Stack                         │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   medsafe_   │      │   medsafe_   │      │   medsafe_   │
│     api      │◄────►│      db      │      │    ollama    │
│              │      │              │      │              │
│ FastAPI      │      │ PostgreSQL   │      │ qwen2.5:7b   │
│ Python 3.10  │      │ + pgvector   │      │ qwen2.5vl:7b │
│              │      │              │      │              │
│ Porta: 9000  │      │ Porta: 5432  │      │ Porta: 11434 │
└──────────────┘      └──────────────┘      └──────────────┘
       │                      │                      │
       └──────────────────────┴──────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  medsafe_network  │
                    │   172.20.0.0/16   │
                    └───────────────────┘
```

### Volumes

```
┌─────────────────────┬──────────────────────────────────┐
│ Volume              │ Conteúdo                         │
├─────────────────────┼──────────────────────────────────┤
│ postgres_data       │ Banco de dados PostgreSQL        │
│ ollama_data         │ Modelos Ollama baixados          │
└─────────────────────┴──────────────────────────────────┘
```

### Portas Expostas

```
┌──────┬─────────────────────────────────────────────────┐
│ Porta│ Serviço                                         │
├──────┼─────────────────────────────────────────────────┤
│ 9000 │ MedSafe API (FastAPI)                           │
│ 5432 │ PostgreSQL (acesso direto ao banco)             │
│ 11434│ Ollama (acesso direto aos modelos)              │
└──────┴─────────────────────────────────────────────────┘
```

---

## 💡 Comandos Úteis

### Gerenciar Containers

```bash
# Listar containers rodando
docker ps

# Listar todos os containers (incluindo parados)
docker ps -a

# Parar container específico
docker stop medsafe_api

# Reiniciar container específico
docker restart medsafe_api

# Remover container específico
docker rm medsafe_api

# Ver logs de container específico
docker logs medsafe_api

# Logs em tempo real
docker logs -f medsafe_api

# Entrar no container (shell)
docker exec -it medsafe_api /bin/bash
```

### Gerenciar Imagens

```bash
# Listar imagens
docker images

# Remover imagem
docker rmi medsafe-api

# Rebuild sem cache
docker-compose build --no-cache

# Pull imagens base atualizadas
docker-compose pull
```

### Gerenciar Volumes

```bash
# Listar volumes
docker volume ls

# Inspecionar volume
docker volume inspect medsafe_postgres_data

# Remover volume (CUIDADO: perde dados!)
docker volume rm medsafe_postgres_data
```

### Banco de Dados

```bash
# Conectar ao PostgreSQL
docker exec -it medsafe_db psql -U medsafe -d medsafe

# Backup do banco
docker exec medsafe_db pg_dump -U medsafe medsafe > backup.sql

# Restaurar banco
cat backup.sql | docker exec -i medsafe_db psql -U medsafe -d medsafe

# Ver tabelas
docker exec -it medsafe_db psql -U medsafe -d medsafe -c "\dt"
```

### Ollama

```bash
# Listar modelos instalados
docker exec medsafe_ollama ollama list

# Baixar modelo adicional
docker exec medsafe_ollama ollama pull llama2

# Remover modelo
docker exec medsafe_ollama ollama rm qwen2.5:7b

# Testar modelo
docker exec medsafe_ollama ollama run qwen2.5:7b "Olá!"
```

### Limpeza

```bash
# Parar tudo e remover containers
docker-compose down

# Parar tudo e remover containers + volumes (perde dados!)
docker-compose down -v

# Remover containers, imagens e volumes órfãos
docker system prune -a --volumes

# Ver espaço usado
docker system df
```

---

## 🐛 Troubleshooting

### 1. Erro: "Cannot connect to Docker daemon"

**Problema:** Docker não está rodando

**Solução:**
```bash
# Linux
sudo systemctl start docker
sudo systemctl enable docker

# macOS/Windows
# Inicie o Docker Desktop
```

---

### 2. Erro: "port is already allocated"

**Problema:** Porta 9000, 5432 ou 11434 já está em uso

**Solução 1:** Parar processo que está usando a porta
```bash
# Ver quem está usando a porta 9000
sudo lsof -i :9000

# Matar processo
sudo kill -9 <PID>
```

**Solução 2:** Mudar porta no `docker-compose.yml`
```yaml
ports:
  - "9001:9000"  # Usar 9001 externamente
```

---

### 3. Containers não iniciam

**Verificar logs:**
```bash
docker-compose logs api
docker-compose logs db
docker-compose logs ollama
```

**Reconstruir imagens:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

### 4. API retorna erro 500

**Verificar logs da API:**
```bash
docker logs -f medsafe_api
```

**Causas comuns:**
- Banco de dados não está pronto (aguardar mais tempo)
- Variáveis de ambiente incorretas (verificar `.env`)
- Migrações do banco não foram executadas

**Solução:**
```bash
# Reiniciar API
docker-compose restart api

# Se persistir, reconstruir
docker-compose down
docker-compose up -d --build
```

---

### 5. Modelos Ollama não funcionam

**Verificar modelos instalados:**
```bash
docker exec medsafe_ollama ollama list
```

**Baixar modelos manualmente:**
```bash
docker exec medsafe_ollama ollama pull qwen2.5:7b
docker exec medsafe_ollama ollama pull qwen2.5vl:7b
```

**Testar modelo:**
```bash
docker exec medsafe_ollama ollama run qwen2.5:7b "Teste"
```

---

### 6. Banco de dados não conecta

**Verificar se PostgreSQL está rodando:**
```bash
docker ps | grep medsafe_db
```

**Testar conexão:**
```bash
docker exec medsafe_db pg_isready -U medsafe
```

**Verificar logs:**
```bash
docker logs medsafe_db
```

**Resetar banco (PERDE DADOS!):**
```bash
docker-compose down -v
docker-compose up -d
```

---

### 7. Sem espaço em disco

**Verificar uso:**
```bash
docker system df
```

**Limpar recursos não usados:**
```bash
# Limpar containers parados
docker container prune

# Limpar imagens não usadas
docker image prune -a

# Limpar volumes não usados
docker volume prune

# Limpar tudo de uma vez (CUIDADO!)
docker system prune -a --volumes
```

---

## 📊 Monitoramento

### Health Checks

```bash
# Verificar saúde da API
curl http://localhost:9000/healthz | jq

# Verificar métricas
curl http://localhost:9000/metrics | jq
```

### Estatísticas em Tempo Real

```bash
# Ver uso de recursos
docker stats

# Ver uso de recursos de containers MedSafe
docker stats $(docker ps --filter "name=medsafe" -q)
```

### Logs Estruturados

```bash
# Logs JSON formatados
docker logs medsafe_api | jq

# Filtrar por nível
docker logs medsafe_api | grep ERROR

# Últimas N linhas
docker logs --tail 100 medsafe_api
```

---

## 🔒 Segurança

### Variáveis de Ambiente

**NUNCA commite o arquivo `.env` no Git!**

O `.env` é criado automaticamente com secrets seguros. Para regenerar:

```bash
# Remover .env
rm .env

# Recriar com novos secrets
./docker-start.sh
```

### Secrets

```bash
# Gerar secrets manualmente
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'

# Editar .env
nano .env
```

---

## 📚 Referências

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL + pgvector](https://github.com/ankane/pgvector)
- [Ollama Documentation](https://ollama.ai/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🆘 Suporte

Se encontrar problemas:

1. ✅ Verifique os logs: `./docker-logs.sh`
2. ✅ Veja o status: `./docker-status.sh`
3. ✅ Consulte [Troubleshooting](#troubleshooting)
4. ✅ Abra uma issue no GitHub

---

**Versão:** 1.2.0
**Data:** 2025-11-12
**Porta padrão:** 9000
