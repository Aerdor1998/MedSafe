# Fix: ModuleNotFoundError no Docker - backend.app.routers.health

**Data**: 2025-11-27
**Status**: ✅ RESOLVIDO
**Severidade**: 🔴 CRÍTICA (bloqueava inicialização da API)

---

## 🐛 Problema

O container `medsafe_api` estava crashando imediatamente ao iniciar com o erro:

```
ModuleNotFoundError: No module named 'backend.app.routers.health'
```

### Sintomas

- Container em crash loop (restart infinito)
- Logs mostravam import failure em `backend/app/main.py:109`
- Health check falhando
- API inacessível

---

## 🔍 Investigação

### Passos de Debug

1. **Verificação local**: Import funcionava fora do Docker ✅
   ```bash
   python3 -c "from backend.app.routers.health import router"
   # ✅ Sucesso
   ```

2. **Verificação de arquivos**: Arquivos existiam no container ✅
   ```bash
   docker run --rm --entrypoint /bin/bash medsafe-api -c "ls /app/backend/app/routers/"
   # health.py presente
   ```

3. **Teste de import no container**: Falha com erro diferente ❌
   ```bash
   docker run --rm --entrypoint /bin/bash medsafe-api -c "python3 -c 'from backend.app.routers.health import router'"
   # ValidationError: secret_key, postgres_password, jwt_secret required
   ```

4. **Verificação de env vars**: Variáveis presentes no container ✅
   ```bash
   docker exec medsafe_api env | grep SECRET_KEY
   # Variáveis presentes
   ```

5. **Causa Raiz Identificada**: Volume mount sobrescrevendo código compilado 🎯

---

## 🔧 Causa Raiz

O `docker-compose.yml` tinha um volume mount que sobrescrevia o código do container:

```yaml
volumes:
  - ./backend:/app/backend  # ❌ PROBLEMA
```

### O que acontecia:

1. **Dockerfile** COPIA `backend/` para `/app/backend/` (código compilado, com cache)
2. **docker-compose.yml** MONTA `./backend` em `/app/backend` (sobrescreve tudo!)
3. Código local pode ter:
   - Cache corrompido (`__pycache__` com permissões de root)
   - Arquivos .pyc desatualizados
   - Diferenças de permissão

### Erro Misleading

O erro "No module named 'backend.app.routers.health'" era **enganoso**. O módulo existia, mas:
- A importação falhava porque `config.py` validava env vars
- Mas como o mount substituía tudo, o Python não conseguia completar o import

---

## ✅ Solução

### 1. **Comentar volume mount do backend** (docker-compose.yml)

```yaml
volumes:
  # SKILL: @debugging-strategies - Backend volume commented to use built version
  # - ./backend:/app/backend  # ❌ Comentado
  - ./logs:/app/logs
  - ./data:/app/data
  - ./static:/app/static
  - ./frontend:/app/frontend
```

### 2. **Mudar import relativo para absoluto** (main.py)

```python
# Antes (import relativo)
from .routers.health import router as health_router

# Depois (import absoluto)
from backend.app.routers.health import router as health_router
```

### 3. **Adicionar dependências faltantes** (requirements.txt)

```python
# Web Scraping (for literature ingestion)
beautifulsoup4
lxml
```

### 4. **Rebuild container sem cache**

```bash
docker-compose down
docker-compose build --no-cache api
docker-compose up -d
```

---

## 📊 Resultado

### Antes

```
❌ Container em crash loop
❌ API inacessível
❌ Health check falhando
❌ Logs: ModuleNotFoundError
```

### Depois

```
✅ Container iniciando normalmente
✅ API rodando em http://localhost:9001
✅ Health check: 200 OK
✅ Logs: "MedSafe API iniciada com sucesso!"
```

### Teste de Funcionamento

```bash
$ curl http://localhost:9001/healthz | jq '.'
{
  "status": "healthy",
  "timestamp": "2025-11-27T17:47:15.540050",
  "version": "2.0.0-langgraph",
  "services": {
    "database": "ok",
    "api": "ok"
  }
}
```

---

## 🎓 Lições Aprendidas

### 1. **Volume Mounts em Development vs Production**

- ✅ **Development**: Útil para hot-reload (edita código e vê mudanças)
- ❌ **Problema**: Pode sobrescrever código compilado e causar inconsistências
- 💡 **Solução**: Usar apenas para arquivos de dados, logs, static files

### 2. **Erros de Import Podem Ser Misleading**

- Erro: "No module named X"
- Real: Módulo existe, mas falha ao ser importado (validação, dependências, etc.)
- Debug: Tentar importar diretamente no Python REPL dentro do container

### 3. **__pycache__ e Permissões**

- Docker pode criar `__pycache__` como root
- Volume mounts misturando código local + container = problemas
- Limpar cache antes de rebuild: `find . -name "*.pyc" -delete`

### 4. **Import Absoluto vs Relativo**

- **Relativo** (`.routers.health`): Funciona em imports normais
- **Absoluto** (`backend.app.routers.health`): Mais robusto para entry points (uvicorn)
- Preferir absoluto em arquivos de entry point

---

## 🔄 Impacto nas Próximas Etapas

### Desenvolvimento Local

Para desenvolvedores que querem hot-reload:

```yaml
# Descomentar apenas se necessário (com cuidado!)
volumes:
  - ./backend:/app/backend
```

**Após editar código local**, rebuild:
```bash
docker-compose restart api
```

### Produção

Volume mount do backend **NUNCA** deve estar habilitado em produção:

```yaml
# docker-compose.prod.yml
volumes:
  # NÃO incluir ./backend:/app/backend
  - ./logs:/app/logs
  - ./data:/app/data
```

---

## 📝 Checklist de Validação

Para verificar se o fix funcionou:

- [x] Container `medsafe_api` inicia sem crashes
- [x] Logs mostram "MedSafe API iniciada com sucesso!"
- [x] `curl http://localhost:9001/healthz` retorna 200 OK
- [x] Banco de dados conectado (logs mostram "✅ Banco de dados inicializado")
- [x] Nenhum erro de import nos logs

---

## 🛠️ Arquivos Modificados

| Arquivo | Mudança | Motivo |
|---------|---------|--------|
| `docker-compose.yml` | Comentar `./backend:/app/backend` | Evitar sobrescrever código compilado |
| `backend/app/main.py` | Import absoluto ao invés de relativo | Compatibilidade com uvicorn |
| `requirements.txt` | Adicionar beautifulsoup4, lxml | Dependências do literature_ingestion.py |

---

## 🔗 Referências

- **Skill Used**: @debugging-strategies - Systematic debugging approach
- **Pattern**: Root cause analysis with hypothesis testing
- **Docker Best Practices**: Volume mounts should be used carefully in containerized apps
- **Python Import System**: Absolute imports are more robust for entry points

---

**Corrigido por**: Claude Code (debugging-strategies skill)
**Tempo de Resolução**: ~30 minutos (10 tentativas de debug)
**Técnica**: Eliminação sistemática de hipóteses + root cause analysis
