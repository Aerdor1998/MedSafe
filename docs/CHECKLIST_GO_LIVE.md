# MedSafe - Checklist de Go-Live para Produção

Este documento contém o checklist completo para deploy em produção.
**Todos os itens BLOCKER devem ser verificados antes do go-live.**

---

## Sumário

1. [Pré-requisitos de Infraestrutura](#1-pré-requisitos-de-infraestrutura)
2. [Configuração de Segurança](#2-configuração-de-segurança)
3. [Compliance LGPD](#3-compliance-lgpd)
4. [Banco de Dados](#4-banco-de-dados)
5. [Monitoramento e Observabilidade](#5-monitoramento-e-observabilidade)
6. [Testes de Validação](#6-testes-de-validação)
7. [Documentação](#7-documentação)
8. [Procedimento de Deploy](#8-procedimento-de-deploy)

---

## 1. Pré-requisitos de Infraestrutura

### Bloqueadores (BLOCKER)

- [ ] **ENVIRONMENT=production** configurado no `.env`
- [ ] **Docker** e **docker-compose** instalados (versão 20.10+)
- [ ] **PostgreSQL 15+** disponível com pgvector extension
- [ ] **Redis** disponível para rate limiting e token revocation
- [ ] **Ollama** configurado com modelos carregados
- [ ] **SSL/TLS** certificado válido configurado (não autoassinado)
- [ ] **DNS** configurado apontando para o servidor
- [ ] **Firewall** configurado (apenas portas 80, 443 expostas)

### Recomendados

- [ ] Load balancer configurado (nginx/HAProxy)
- [ ] CDN para assets estáticos
- [ ] GPU disponível para Ollama (recomendado 8GB+ VRAM)

### Validação

```bash
# Verificar Docker
docker --version && docker-compose --version

# Verificar PostgreSQL com pgvector
docker exec -it medsafe-db psql -U medsafe -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# Verificar Redis
docker exec -it medsafe-redis redis-cli ping

# Verificar Ollama
curl -s http://localhost:11434/api/version

# Verificar SSL
curl -sI https://medsafe.example.com | grep -E "^HTTP|^server"
```

---

## 2. Configuração de Segurança

### Bloqueadores (BLOCKER)

- [ ] **SECRET_KEY** configurado (≥32 caracteres, alta entropia)
- [ ] **JWT_SECRET** configurado (≥32 caracteres, alta entropia)
- [ ] **POSTGRES_PASSWORD** configurado (≥16 caracteres)
- [ ] **DEBUG=false** em produção
- [ ] **ALLOWED_ORIGINS** sem wildcard (*)
- [ ] **ALLOWED_HOSTS** sem wildcard (*)
- [ ] **ENABLE_LOG_REDACTION=true** para LGPD
- [ ] **Rate limiting** ativo via Redis

### Recomendados

- [ ] JWT_KEY_VERSION incrementado desde staging
- [ ] JWT_ENABLE_REVOCATION=true
- [ ] CSP_STRICT_MODE=true (se frontend preparado)
- [ ] HSTS_ENABLED=true

### Validação

```bash
# Verificar secrets não são default (aplicação deve iniciar sem erros)
docker-compose -f docker-compose.prod.yml run --rm api python -c "
from backend.app.config import settings
print('✓ Environment:', settings.environment)
print('✓ Debug:', settings.debug)
print('✓ Log Redaction:', settings.enable_log_redaction)
assert settings.environment == 'production', 'ENVIRONMENT deve ser production'
assert not settings.debug, 'DEBUG deve ser false'
assert settings.enable_log_redaction, 'ENABLE_LOG_REDACTION deve ser true'
print('✅ Todas validações de segurança passaram!')
"

# Verificar que valores default são bloqueados
# (este comando DEVE falhar em produção se secrets são default)
ENVIRONMENT=production SECRET_KEY=CHANGE_ME python -c "from backend.app.config import Settings; Settings()"
# Esperado: ValueError

# Testar rate limiting
for i in $(seq 1 50); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/api/v2/health)
  echo "Request $i: $CODE"
done | grep "429" && echo "✅ Rate limiting ativo"
```

---

## 3. Compliance LGPD

### Bloqueadores (BLOCKER)

- [ ] **Data retention worker** configurado para execução periódica
- [ ] **Soft delete** implementado em tabelas com PHI (triage, reports, hitl_reviews)
- [ ] **Log redaction** ativo e testado
- [ ] **Audit logs** configurados para operações sensíveis
- [ ] **Termo de consentimento** implementado no frontend

### Recomendados

- [ ] Backup offsite configurado (S3, GCS, Azure Blob)
- [ ] Criptografia em repouso (DATA_ENCRYPTION_AT_REST=true)
- [ ] Política de retenção documentada e revisada por jurídico

### Validação

```bash
# Verificar colunas de soft delete existem
docker exec -it medsafe-db psql -U medsafe -c "
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('is_deleted', 'deleted_at', 'deleted_by')
ORDER BY table_name;
"

# Verificar índices de soft delete
docker exec -it medsafe-db psql -U medsafe -c "
SELECT indexname FROM pg_indexes
WHERE indexname LIKE '%is_deleted%' OR indexname LIKE '%active%';
"

# Testar log redaction (simular dado sensível nos logs)
docker exec -it medsafe-api python -c "
from backend.app.utils.log_redaction import redact_sensitive_data
test_data = 'CPF: 123.456.789-00, email: user@test.com, tel: (11) 99999-9999'
result = redact_sensitive_data(test_data)
assert '[REDACTED-CPF]' in result, 'CPF não foi redactado!'
assert '[REDACTED-EMAIL]' in result, 'Email não foi redactado!'
print('✅ Log redaction funcionando corretamente')
print('Resultado:', result)
"
```

---

## 4. Banco de Dados

### Bloqueadores (BLOCKER)

- [ ] **Migrations** aplicadas (`alembic upgrade head`)
- [ ] **Índices** criados para queries frequentes
- [ ] **Backup** inicial realizado e testado
- [ ] **Cron de backup** configurado (mínimo: horário)
- [ ] **pgvector** extension instalada

### Recomendados

- [ ] Connection pooling configurado (PgBouncer)
- [ ] Réplica de leitura configurada
- [ ] Vacuum automático configurado

### Validação

```bash
# Verificar migrations
docker exec -it medsafe-db psql -U medsafe -c "
SELECT version_num FROM alembic_version;
"

# Verificar índices críticos
docker exec -it medsafe-db psql -U medsafe -c "
SELECT indexname, tablename FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename;
"

# Testar backup
./scripts/db-backup.sh backup
./scripts/db-backup.sh list

# Verificar integridade do backup
gunzip -t backups/medsafe_backup_*.sql.gz && echo "✅ Backup íntegro"
```

---

## 5. Monitoramento e Observabilidade

### Bloqueadores (BLOCKER)

- [ ] **Health check** endpoint funcionando (`/health`)
- [ ] **Métricas Prometheus** expostas (`/metrics`)
- [ ] **Alertas críticos** configurados (API down, DB down, worker down)
- [ ] **Logs** centralizados e acessíveis

### Recomendados

- [ ] Grafana dashboards configurados
- [ ] Alertas de latência (P95 > 2s)
- [ ] Alertas de error rate (> 5%)
- [ ] Alertas de HITL queue (> 25 pendentes)

### Validação

```bash
# Testar health check
curl -s http://localhost:9000/health | jq .

# Verificar métricas disponíveis
curl -s http://localhost:9000/metrics | grep -E "^medsafe_" | head -20

# Verificar alertas Prometheus
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'
```

---

## 6. Testes de Validação

### Bloqueadores (BLOCKER)

- [ ] **Testes unitários** passando (>80% coverage)
- [ ] **Testes de integração** passando
- [ ] **Teste de carga** executado (mínimo 50 req/s por 5 min)
- [ ] **Teste de segurança** executado (OWASP ZAP ou similar)

### Recomendados

- [ ] Teste de chaos engineering (kill random container)
- [ ] Teste de failover de banco
- [ ] Teste de restore de backup

### Validação

```bash
# Rodar testes
pytest backend/tests/ -v --cov=backend/app --cov-report=term-missing

# Verificar coverage mínimo
pytest backend/tests/ --cov=backend/app --cov-fail-under=80

# Teste de smoke básico (após deploy)
curl -s http://localhost:9000/health | jq -e '.status == "healthy"'
curl -s http://localhost:9000/api/v2/health | jq -e '.status == "ok"'
```

---

## 7. Documentação

### Bloqueadores (BLOCKER)

- [ ] **Runbook de operações** atualizado
- [ ] **Contatos de escalação** definidos
- [ ] **Procedimento de rollback** documentado

### Recomendados

- [ ] Documentação de API atualizada (/docs)
- [ ] Changelog atualizado
- [ ] README com instruções de deploy

### Validação

```bash
# Verificar documentos existem
ls -la docs/RUNBOOK_OPERACOES.md
ls -la docs/CHECKLIST_GO_LIVE.md
ls -la docs/API_MIGRATION_V1_TO_V2.md

# Verificar Swagger disponível
curl -s http://localhost:9000/docs | grep -q "swagger" && echo "✅ Swagger disponível"
```

---

## 8. Procedimento de Deploy

### Pré-deploy

```bash
# 1. Verificar branch e tag
git status
git tag -l | tail -5

# 2. Criar tag de release
git tag -a v1.0.0-prod -m "Production release"
git push origin v1.0.0-prod

# 3. Backup do banco atual
./scripts/db-backup.sh backup
```

### Deploy

```bash
# 4. Pull das imagens/código
git pull origin main
docker-compose -f docker-compose.prod.yml pull

# 5. Aplicar migrations
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 6. Deploy com rolling update
docker-compose -f docker-compose.prod.yml up -d --remove-orphans

# 7. Aguardar containers healthy
sleep 30
docker-compose -f docker-compose.prod.yml ps
```

### Pós-deploy

```bash
# 8. Validar saúde
curl -s http://localhost:9000/health | jq .

# 9. Verificar logs por erros
docker-compose -f docker-compose.prod.yml logs --tail 100 | grep -i error

# 10. Testar funcionalidade crítica
curl -s http://localhost:9000/api/v2/health | jq .

# 11. Monitorar métricas por 15 minutos
watch -n 5 'curl -s http://localhost:9000/metrics | grep medsafe_http_requests_total'
```

### Rollback (se necessário)

```bash
# Em caso de problemas críticos:

# 1. Reverter para versão anterior
docker-compose -f docker-compose.prod.yml down
git checkout v0.9.9-prod  # tag anterior
docker-compose -f docker-compose.prod.yml up -d

# 2. Se migrations precisam rollback
docker-compose -f docker-compose.prod.yml run --rm api alembic downgrade -1

# 3. Se dados corrompidos, restaurar backup
./scripts/db-backup.sh restore backups/pre_deploy_backup.sql.gz
```

---

## Matriz de Aprovação

| Área | Responsável | Status | Data |
|------|-------------|--------|------|
| Infraestrutura | DevOps Lead | ⬜ | |
| Segurança | Security Team | ⬜ | |
| Compliance LGPD | DPO | ⬜ | |
| Banco de Dados | DBA | ⬜ | |
| Aplicação | Tech Lead | ⬜ | |
| Negócio | Product Owner | ⬜ | |

---

## Histórico de Revisões

| Versão | Data | Autor | Mudanças |
|--------|------|-------|----------|
| 1.0 | 2026-01-14 | MedSafe Team | Versão inicial |

---

*Última atualização: 2026-01-14*
