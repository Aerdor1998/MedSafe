# MedSafe - Runbook de Operações

Este documento fornece procedimentos de resposta a incidentes para operadores do sistema MedSafe.

## Índice

1. [Alertas Críticos](#alertas-críticos)
2. [Procedimentos de Diagnóstico](#procedimentos-de-diagnóstico)
3. [Procedimentos de Recuperação](#procedimentos-de-recuperação)
4. [Contatos de Escalação](#contatos-de-escalação)

---

## Alertas Críticos

### 1. MedSafeAPIDown

**Severidade**: Crítica
**Impacto**: Sistema completamente indisponível para usuários

**Diagnóstico**:
```bash
# Verificar status dos containers
docker ps -a | grep medsafe

# Verificar logs do container
docker logs medsafe-api --tail 100

# Verificar uso de recursos
docker stats medsafe-api
```

**Recuperação**:
```bash
# Reiniciar o serviço
docker-compose restart api

# Se persistir, reiniciar todo o stack
docker-compose down && docker-compose up -d
```

**Escalação**: Se não resolver em 5 minutos, escalar para equipe de infra.

---

### 2. MedSafeWorkerDown

**Severidade**: Crítica
**Impacto**: Análises não são processadas; fila cresce

**Diagnóstico**:
```bash
# Verificar status do worker
docker ps -a | grep medsafe-worker

# Verificar logs
docker logs medsafe-worker --tail 100

# Verificar jobs pendentes no banco
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT status, count(*) FROM analysis_jobs GROUP BY status;"
```

**Recuperação**:
```bash
# Reiniciar worker
docker-compose restart worker

# Verificar se jobs retomaram
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT status, count(*) FROM analysis_jobs WHERE created_at > now() - interval '1 hour' GROUP BY status;"
```

---

### 3. MedSafeHITLQueueCritical

**Severidade**: Crítica (Clínica)
**Impacto**: Análises de alto risco aguardando revisão médica

**Diagnóstico**:
```bash
# Contar revisões pendentes
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT count(*) as pending FROM analysis_jobs WHERE status = 'awaiting_review';"

# Listar revisões mais antigas
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT session_id, created_at, state->>'risk_level' as risk
   FROM analysis_jobs 
   WHERE status = 'awaiting_review' 
   ORDER BY created_at ASC LIMIT 10;"
```

**Ação**:
1. Notificar equipe clínica imediatamente
2. Priorizar revisões com `risk_level = 'grave'`
3. Se necessário, aumentar capacidade de revisão

**Escalação**: Coordenador clínico deve ser notificado após 15 minutos sem progresso.

---

### 4. MedSafeOllamaDown

**Severidade**: Crítica
**Impacto**: Análises LLM falham; sistema degradado

**Diagnóstico**:
```bash
# Verificar container Ollama
docker ps -a | grep ollama

# Testar endpoint
curl http://localhost:11434/api/version

# Verificar uso de GPU
nvidia-smi
```

**Recuperação**:
```bash
# Reiniciar Ollama
docker-compose restart ollama

# Verificar se modelo está carregado
curl http://localhost:11434/api/tags

# Se modelo não carregou, puxar novamente
docker exec -it ollama ollama pull qwen3:8b
```

---

### 5. MedSafeDBDown

**Severidade**: Crítica
**Impacto**: Sistema completamente inoperante

**Diagnóstico**:
```bash
# Verificar container PostgreSQL
docker ps -a | grep postgres

# Verificar logs
docker logs medsafe-db --tail 100

# Testar conexão
docker exec -it medsafe-db pg_isready -U medsafe
```

**Recuperação**:
```bash
# Reiniciar PostgreSQL
docker-compose restart db

# Verificar integridade
docker exec -it medsafe-db psql -U medsafe -c "SELECT 1;"

# Se dados corrompidos, restaurar backup (ver seção abaixo)
```

---

### 6. MedSafeAuthFailuresSpike

**Severidade**: Crítica (Segurança)
**Impacto**: Possível ataque de credential stuffing

**Diagnóstico**:
```bash
# Verificar padrão de falhas nos logs
docker logs medsafe-api 2>&1 | grep "login_failed" | tail -50

# Verificar IPs com muitas tentativas
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT details->>'client_ip' as ip, count(*) 
   FROM audit_logs 
   WHERE event_type = 'login_failure' 
     AND created_at > now() - interval '1 hour'
   GROUP BY details->>'client_ip' 
   ORDER BY count(*) DESC LIMIT 10;"
```

**Ação**:
1. Identificar IPs com muitas tentativas
2. Avaliar bloqueio temporário via WAF/firewall
3. Verificar se contas específicas estão sendo targetadas
4. Considerar ativar CAPTCHA ou aumentar rate limiting

**Escalação**: Equipe de segurança deve ser notificada imediatamente.

---

## Procedimentos de Diagnóstico

### Verificar Saúde Geral do Sistema

```bash
# Health check completo
curl http://localhost:9000/health

# Verificar métricas
curl http://localhost:9000/metrics | grep medsafe_

# Status de todos os containers
docker-compose ps
```

### Verificar Logs em Tempo Real

```bash
# Todos os serviços
docker-compose logs -f

# Apenas API
docker-compose logs -f api

# Apenas Worker
docker-compose logs -f worker
```

### Verificar Estado do Banco

```bash
# Conexões ativas
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'medsafe';"

# Jobs por status
docker exec -it medsafe-db psql -U medsafe -c \
  "SELECT status, count(*), 
          avg(EXTRACT(epoch FROM (finished_at - started_at))) as avg_duration
   FROM analysis_jobs 
   WHERE created_at > now() - interval '24 hours'
   GROUP BY status;"
```

---

## Procedimentos de Recuperação

### Backup e Disaster Recovery

#### Objetivos de Recuperação

| Métrica | Valor | Descrição |
|---------|-------|-----------|
| **RPO** (Recovery Point Objective) | 1 hora | Perda máxima de dados aceitável |
| **RTO** (Recovery Time Objective) | 4 horas | Tempo máximo para restaurar serviço |
| **Retenção de Backups** | 30 dias | Backups disponíveis para restore |

#### Executar Backup Manual

```bash
# Backup completo do banco de dados
./scripts/db-backup.sh backup

# Verificar backup criado
./scripts/db-backup.sh list

# Saída esperada:
# [INFO] Available backups in ./backups:
# -rw-r--r-- 1 user user 2.5M Jan 14 10:00 medsafe_backup_20260114_100000.sql.gz
```

#### Backup Automático via Cron

Configurar cron para backup a cada hora:

```bash
# Adicionar ao crontab do servidor
crontab -e

# Adicionar linha (backup a cada hora, às HH:00):
0 * * * * /path/to/medsafe/scripts/db-backup.sh backup >> /var/log/medsafe-backup.log 2>&1
```

#### Validar Integridade de Backup

```bash
# 1. Verificar se arquivo não está corrompido
gunzip -t backups/medsafe_backup_*.sql.gz && echo "OK: Backup íntegro"

# 2. Verificar tamanho mínimo (backups < 1KB são suspeitos)
find backups/ -name "*.sql.gz" -size +1k -ls

# 3. Verificar conteúdo (amostra)
zcat backups/medsafe_backup_*.sql.gz | head -50 | grep -E "^(CREATE|INSERT|--)"

# 4. Teste de restore em banco temporário (recomendado semanal)
docker run --rm -d --name medsafe_restore_test postgres:15-alpine
sleep 5
zcat backups/medsafe_backup_latest.sql.gz | docker exec -i medsafe_restore_test psql -U postgres
echo "SELECT count(*) FROM triage;" | docker exec -i medsafe_restore_test psql -U postgres
docker stop medsafe_restore_test
```

#### Restaurar Backup do Banco

**⚠️ ATENÇÃO: Este procedimento SUBSTITUI todos os dados atuais!**

```bash
# 1. Comunicar equipe sobre manutenção
# 2. Parar aplicação (impedir escritas)
docker-compose stop api worker

# 3. Criar backup do estado atual (safety net)
./scripts/db-backup.sh backup
mv backups/medsafe_backup_*.sql.gz backups/pre_restore_backup.sql.gz

# 4. Identificar backup para restore
./scripts/db-backup.sh list

# 5. Restaurar (requer confirmação interativa)
./scripts/db-backup.sh restore backups/medsafe_backup_20260114_100000.sql.gz

# 6. Verificar integridade pós-restore
docker exec -it medsafe-db psql -U medsafe -c "
SELECT
  (SELECT count(*) FROM triage) as triages,
  (SELECT count(*) FROM reports) as reports,
  (SELECT count(*) FROM analysis_jobs) as jobs;
"

# 7. Reiniciar aplicação
docker-compose start api worker

# 8. Validar funcionamento
curl http://localhost:9000/health
```

#### Disaster Recovery Completo

Em caso de perda total do servidor:

```bash
# 1. Provisionar novo servidor com Docker e docker-compose

# 2. Clonar repositório
git clone https://github.com/org/medsafe.git
cd medsafe

# 3. Configurar variáveis de ambiente
cp env.example .env
# Editar .env com secrets de produção (recuperar do Vault/Secret Manager)

# 4. Subir infraestrutura
docker-compose -f docker-compose.prod.yml up -d db

# 5. Restaurar backup mais recente (do storage externo/S3)
aws s3 cp s3://medsafe-backups/latest/medsafe_backup.sql.gz backups/
./scripts/db-backup.sh restore backups/medsafe_backup.sql.gz

# 6. Aplicar migrations pendentes
docker-compose run --rm api alembic upgrade head

# 7. Subir demais serviços
docker-compose -f docker-compose.prod.yml up -d

# 8. Validar todos os serviços
./scripts/docker-status.sh
curl http://localhost:9000/health
```

#### Backup Offsite (Recomendado para Produção)

Configurar sync automático para storage externo:

```bash
# Adicionar ao cron (diário às 02:00)
0 2 * * * aws s3 sync /path/to/medsafe/backups s3://medsafe-backups/$(date +\%Y-\%m-\%d)/ --delete

# Ou usar rclone para outros providers
0 2 * * * rclone sync /path/to/medsafe/backups remote:medsafe-backups/$(date +\%Y-\%m-\%d)/
```

### Limpar Fila de Jobs Travados

```bash
# Identificar jobs travados (running por mais de 1 hora)
docker exec -it medsafe-db psql -U medsafe -c \
  "UPDATE analysis_jobs 
   SET status = 'failed', 
       last_error = 'Force reset by operator'
   WHERE status = 'running' 
     AND started_at < now() - interval '1 hour';"

# Reiniciar worker para processar novamente
docker-compose restart worker
```

### Reprocessar Jobs Falhados

```bash
# Recolocar jobs falhados como pendentes (com retry limit)
docker exec -it medsafe-db psql -U medsafe -c \
  "UPDATE analysis_jobs 
   SET status = 'pending', 
       retries = retries + 1
   WHERE status = 'failed' 
     AND retries < 3
     AND created_at > now() - interval '24 hours';"
```

---

## Contatos de Escalação

| Nível | Equipe | Canal | Tempo Resposta |
|-------|--------|-------|----------------|
| L1 | Operações | #ops-medsafe | 15 min |
| L2 | Backend | #backend-oncall | 30 min |
| L3 | Infra | #infra-critical | 1 hora |
| Clínico | Médico Plantonista | Tel: XXX-XXXX | Imediato |
| Segurança | SecOps | #security-incident | 15 min |

---

## Checklist de Incidente

- [ ] Identificar severidade do incidente
- [ ] Comunicar equipe via canal apropriado
- [ ] Coletar logs e evidências
- [ ] Executar procedimento de recuperação
- [ ] Validar que serviço está restaurado
- [ ] Documentar timeline e ações tomadas
- [ ] Agendar post-mortem se necessário

---

## Métricas Chave para Monitoramento

| Métrica | Normal | Alerta | Crítico |
|---------|--------|--------|---------|
| API Latency P95 | < 500ms | > 1s | > 2s |
| Error Rate | < 1% | > 3% | > 5% |
| Jobs Pendentes | < 10 | > 50 | > 100 |
| HITL Queue | < 5 | > 10 | > 25 |
| DB Connections | < 50% | > 80% | > 90% |
| LLM Latency | < 15s | > 30s | > 60s |

---

---

## LGPD Compliance e Retenção de Dados

### Políticas de Retenção Configuradas

| Tabela | Retenção | Tipo | Base Legal |
|--------|----------|------|------------|
| `triage` | 5 anos | Soft delete | CFM Res. 1821/2007 |
| `reports` | 5 anos | Soft delete | CFM Res. 1821/2007 |
| `hitl_reviews` | 5 anos | Soft delete | Auditoria médica |
| `analysis_jobs` | 1 ano | Hard delete | Dados operacionais |
| `audit_logs` | 5 anos | Hard delete | LGPD Art. 37 |
| `ingest_jobs` | 6 meses | Hard delete | Dados operacionais |

### Executar Data Retention Worker

```bash
# Execução manual (uma vez)
RETENTION_RUN_ONCE=true python -m backend.app.workers.data_retention_worker

# Execução contínua (daemon)
python -m backend.app.workers.data_retention_worker

# Via docker-compose
docker-compose run --rm api python -m backend.app.workers.data_retention_worker
```

### Verificar Registros Marcados para Exclusão

```bash
# Contar registros soft-deleted por tabela
docker exec -it medsafe-db psql -U medsafe -c "
SELECT 'triage' as table_name, count(*) as soft_deleted FROM triage WHERE is_deleted = true
UNION ALL
SELECT 'reports', count(*) FROM reports WHERE is_deleted = true
UNION ALL
SELECT 'hitl_reviews', count(*) FROM hitl_reviews WHERE is_deleted = true
UNION ALL
SELECT 'analysis_jobs', count(*) FROM analysis_jobs WHERE is_deleted = true;
"
```

### Atender Requisição de Exclusão de Dados (LGPD Art. 18)

Quando um titular solicita exclusão de seus dados:

```bash
# 1. Identificar registros do titular (por user_id ou session)
docker exec -it medsafe-db psql -U medsafe -c "
SELECT t.id, t.created_at, t.is_deleted,
       (SELECT count(*) FROM reports r WHERE r.triage_id = t.id) as reports
FROM triage t
WHERE t.user_id = 'USER_ID_AQUI';
"

# 2. Executar soft delete com justificativa LGPD
docker exec -it medsafe-db psql -U medsafe -c "
UPDATE triage SET
  is_deleted = true,
  deleted_at = NOW(),
  deleted_by = 'OPERATOR_ID',
  deletion_reason = 'LGPD Art. 18 - Solicitação do titular'
WHERE user_id = 'USER_ID_AQUI' AND is_deleted = false;
"

# 3. Soft delete de reports relacionados
docker exec -it medsafe-db psql -U medsafe -c "
UPDATE reports SET
  is_deleted = true,
  deleted_at = NOW(),
  deleted_by = 'OPERATOR_ID'
WHERE triage_id IN (SELECT id FROM triage WHERE user_id = 'USER_ID_AQUI')
  AND is_deleted = false;
"

# 4. Registrar no audit_log (obrigatório)
docker exec -it medsafe-db psql -U medsafe -c "
INSERT INTO audit_logs (id, event_type, severity, actor_id, actor_type, resource_type, details, created_at)
VALUES (
  gen_random_uuid(),
  'lgpd_data_deletion_request',
  'warning',
  'OPERATOR_ID',
  'operator',
  'user_data',
  '{\"user_id\": \"USER_ID_AQUI\", \"reason\": \"LGPD Art. 18\", \"tables_affected\": [\"triage\", \"reports\"]}',
  NOW()
);
"
```

### Verificar Log Redaction Ativo

```bash
# Verificar configuração atual
docker exec -it medsafe-api printenv | grep ENABLE_LOG_REDACTION

# Testar redação em logs (deve mostrar [REDACTED])
docker logs medsafe-api 2>&1 | grep -E "(cpf|email|phone)" | head -5
# Se encontrar dados sensíveis não-redactados, escalar imediatamente!
```

---

## Verificações de Segurança

### Verificar Secrets em Produção

```bash
# Verificar que secrets não são valores default
docker exec -it medsafe-api python -c "
from backend.app.config import settings
print('Environment:', settings.environment)
print('Secret Key (first 8 chars):', settings.secret_key[:8] + '...')
print('JWT Secret (first 8 chars):', settings.jwt_secret[:8] + '...')
print('Log Redaction Enabled:', settings.enable_log_redaction)
"
```

### Verificar Certificados SSL

```bash
# Verificar expiração do certificado
echo | openssl s_client -servername medsafe.example.com -connect medsafe.example.com:443 2>/dev/null | \
  openssl x509 -noout -dates

# Alertar se expira em menos de 30 dias
```

### Verificar Rate Limiting Ativo

```bash
# Testar rate limiting (deve falhar após N tentativas)
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9000/api/v2/health
done
# Deve retornar 429 após exceder limite
```

---

*Última atualização: 2026-01-14*
*Versão: 1.1*

