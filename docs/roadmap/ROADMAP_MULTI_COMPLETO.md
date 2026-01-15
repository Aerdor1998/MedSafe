🚨 Fase 0: Bloqueadores Críticos (Pré-Produção)
Prazo: 3-5 dias úteis
Esforço Total: 40-60 horas
Status: ⛔ BLOQUEADOR DE PRODUÇÃO
🔴 1. Corrigir Bug de Refresh Token
Esforço: 4-6 horas | Impacto: CRÍTICO
Fonte: Opus 4.5
Problema identificado:

Função verify_token rejeita todos os refresh tokens
Sistema de autenticação efetivamente quebrado
Impossível renovar sessões de usuários

Tarefas:

 Criar função separada para verificar refresh tokens
 Ou modificar verify_token para aceitar parâmetro de tipo esperado
 Adicionar claims JWT de segurança (jti, aud, iss)
 Implementar rotação de refresh tokens
 Criar testes automatizados para refresh flow
 Testar cenário de token expirado
 Testar cenário de token revogado
 Documentar novo fluxo de refresh


🔴 2. Implementar RBAC Real (Remover Placeholder)
Esforço: 8-12 horas | Impacto: CRÍTICO
Fonte: Todos os relatórios
Problema identificado:

RoleChecker retorna usuário sem verificar permissões
Qualquer usuário autenticado tem acesso de admin
Sistema de permissões completamente inoperante

Tarefas:

 Implementar verificação real de roles no banco de dados
 Implementar hierarquia de roles (ADMIN > PHYSICIAN > PHARMACIST > READONLY)
 Criar função de verificação de herança de permissões
 Implementar PermissionChecker com consulta ao BD
 Adicionar logging de tentativas de acesso negado
 Criar testes para cada nível de role
 Testar hierarquia de permissões
 Adicionar auditoria de acessos não autorizados
 Documentar matriz de permissões


🔴 3. Aplicar SecurityHeadersMiddleware ao App
Esforço: 2-3 horas | Impacto: CRÍTICO
Fonte: Opus 4.5
Problema identificado:

Middleware de segurança existe mas não está adicionado ao FastAPI
Respostas sem headers de proteção (CSP, HSTS, X-Frame-Options)
Aplicação vulnerável a XSS, Clickjacking e outros ataques

Tarefas:

 Adicionar SecurityHeadersMiddleware ao app.py
 Melhorar CSP removendo 'unsafe-inline'
 Implementar sistema de nonces para CSP
 Configurar HSTS com preload
 Adicionar Permissions-Policy restritiva
 Remover headers informativos do servidor
 Testar headers em ambiente de desenvolvimento
 Validar com Mozilla Observatory
 Testar com ferramentas de scan de segurança


🔴 4. Corrigir TrustedHostMiddleware (Remover Wildcard)
Esforço: 1-2 horas | Impacto: CRÍTICO
Fonte: Todos os relatórios
Problema identificado:

Configuração com allowed_hosts=["*"] em produção
Não protege contra Host header attacks
Permite ataques de cache poisoning

Tarefas:

 Adicionar variável de ambiente ALLOWED_HOSTS
 Validar que wildcard não pode ser usado em produção
 Configurar hosts específicos por ambiente
 Adicionar validação no Settings
 Configurar redirecionamento www
 Documentar configuração por ambiente
 Testar com hosts válidos e inválidos
 Atualizar guia de deployment


🔴 5. Sanitizar Output HTML no Frontend (Prevenir XSS)
Esforço: 3-4 horas | Impacto: CRÍTICO
Fonte: Texto 2 (Desconhecido)
Problema identificado:

Função formatSummaryText() injeta HTML diretamente
Uso de innerHTML sem sanitização
Vulnerabilidade XSS crítica no cliente

Tarefas:

 Integrar biblioteca DOMPurify
 Configurar whitelist de tags permitidas
 Sanitizar todos os outputs antes de renderizar
 Substituir innerHTML por textContent onde possível
 Implementar CSP nonces no frontend
 Testar com payloads XSS comuns
 Scan com OWASP ZAP
 Documentar práticas de segurança frontend


🔴 6. Ajustar Configuração GPU do Ollama
Esforço: 2-3 horas | Impacto: CRÍTICO
Fonte: Opus 4.5
Problema identificado:

OLLAMA_NUM_GPU=99 pode derrubar servidores
OLLAMA_GPU_LAYERS=99 carrega tudo na VRAM
Sem detecção adaptativa de recursos

Tarefas:

 Reduzir configuração padrão para valores seguros (1 GPU, 32 layers)
 Criar script de detecção automática de GPUs
 Adicionar configuração via variáveis de ambiente
 Criar perfil docker-compose para CPU-only
 Configurar limites de recursos no Docker
 Adicionar reservations de GPU no deploy
 Testar em máquina sem GPU
 Testar com 1, 2 e 4 GPUs
 Documentar requisitos de hardware


📊 Checklist Fase 0 - Aprovação para Produção

**Atualização (2025-12-16):** checklist reconciliado com o estado atual do repositório.

| Item | Status | Bloqueador? | Evidência no repo |
|------|--------|-------------|-------------------|
| Refresh Token bug / rotação | ✅ Completo | ✅ SIM | `backend/app/routers/auth.py` (refresh com rotação + revoke), `backend/app/auth/jwt.py` |
| RBAC real | ✅ Completo | ✅ SIM | `backend/app/auth/rbac.py`, testes em `backend/tests/test_auth_rbac.py` |
| Security headers | ✅ Completo | ✅ SIM | `backend/app/middleware/security.py`, `infra/nginx/nginx.conf` |
| Trusted hosts | ✅ Completo | ✅ SIM | `backend/app/middleware/__init__.py` (TrustedHostMiddleware em produção) |
| XSS Frontend | ✅ Completo | ✅ SIM | `frontend/index.html` (DOMPurify), `frontend/js/app.js` (sanitização) |
| GPU config (Ollama) | ✅ Completo | ✅ SIM | `docker-compose.yml` (defaults seguros + limits) |

Critério de Aprovação: Todos os 6 itens devem estar ✅ COMPLETOS antes de produção.

🟡 Fase 1: Curto Prazo (1-2 semanas)
Prazo: 10 dias úteis
Esforço Total: 80-120 horas
Status: 🟡 ALTA PRIORIDADE
🟡 1. Melhorar Segurança JWT
Esforço: 8-12 horas | Impacto: ALTO
Fonte: Opus 4.5, GPT 5.1 Codex
Tarefas:

 Separar secrets de access e refresh tokens
 Implementar blacklist de tokens com Redis
 Adicionar JTI (unique token ID) a todos os tokens
 Adicionar audience e issuer claims
 Implementar endpoint de logout com revogação
 Adicionar device_id tracking
 Criar sistema de revogação de tokens
 Implementar logout em múltiplos dispositivos
 Testar revogação e reuso de tokens
 Documentar fluxo de tokens aprimorado


🟡 2. Proteger ou Remover Endpoints Legacy V1
Esforço: 6-8 horas | Impacto: ALTO
Fonte: Opus 4.5
Problema identificado:

Endpoints v1 deprecated expostos sem autenticação
Endpoints de triage, vision, ingest e meds sem proteção
Potencial vazamento de dados sensíveis

Opção A: Adicionar Autenticação

 Adicionar dependências de autenticação JWT
 Adicionar RBAC requirements (physician/admin)
 Atualizar documentação de API v1
 Notificar usuários da mudança

Opção B: Feature Flag com Deprecação Gradual (Recomendado)

 Criar flag ENABLE_LEGACY_V1 (padrão: false)
 Adicionar middleware de aviso de deprecação
 Incluir headers X-API-Deprecated e X-API-Sunset
 Criar guia de migração v1 → v2
 Notificar usuários com 60 dias de antecedência
 Agendar remoção completa

Opção C: Remover Completamente

 Remover routers v1 do main.py
 Criar endpoint de redirecionamento com HTTP 410 (Gone)
 Atualizar toda documentação
 Comunicar remoção aos stakeholders

Decisão: Implementar Opção B por 2 meses, depois Opção C

🟡 3. Aumentar Cobertura de Testes para 80%+
Esforço: 20-30 horas | Impacto: ALTO
Fonte: Todos os relatórios
Áreas sem cobertura adequada:
3.1 Testes de Autenticação

 Testar fluxo completo de login
 Testar refresh token rotation
 Testar revogação de tokens
 Testar expiração de access e refresh tokens
 Testar múltiplas sessões simultâneas
 Testar logout em dispositivo específico
 Testar logout em todos os dispositivos

3.2 Testes de RBAC

 Testar hierarquia de roles (ADMIN > PHYSICIAN > PHARMACIST > READONLY)
 Testar herança de permissões
 Testar acesso negado por role insuficiente
 Testar acesso negado por permissão faltante
 Testar auditoria de acessos negados
 Testar edge cases de permissões

3.3 Testes de Agentes LangGraph

 Testar TriageAgent com dados válidos/inválidos
 Testar DocumentAgent com RAG
 Testar ClinicalAgent com 191k+ interações
 Testar ReflectionAgent com refinamento iterativo
 Testar limite de 3 ciclos de reflexão
 Testar SafetyAgent com guardrails
 Testar HITLAgent com interrupt e resume
 Testar checkpointing no PostgreSQL
 Testar fallback quando checkpointer indisponível

3.4 Testes de Segurança

 Testar prevenção de XSS
 Testar prevenção de SQL injection
 Testar prevenção de CSRF
 Testar rate limiting por IP
 Testar rate limiting por user_id
 Testar upload de arquivos maliciosos
 Testar validação de magic bytes

3.5 Testes de Performance

 Benchmark de RAG query (<2s)
 Benchmark de análise clínica (<5s)
 Benchmark de workflow completo (<15s)
 Teste de carga com 100 usuários simultâneos
 Teste de stress até breaking point
 Teste de recuperação após falha

Meta: Cobertura geral ≥ 80% (atual: 70%)

🟡 4. Implementar Testes End-to-End (E2E)
Esforço: 12-16 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex, Texto 2
Tarefas:
4.1 Setup de E2E

 Instalar e configurar Playwright
 Criar ambiente de testes isolado
 Configurar fixtures de dados de teste
 Configurar captura de screenshots em falhas
 Configurar gravação de vídeos de testes

4.2 Testes de Workflows Principais

 E2E: Login e autenticação completa
 E2E: Criação de triagem com dados válidos
 E2E: Upload de prescrição médica
 E2E: Análise completa de contraindicações
 E2E: Workflow HITL (interrupt e aprovação)
 E2E: Geração e download de relatório
 E2E: Busca de medicamentos
 E2E: Navegação entre páginas
 E2E: Logout e limpeza de sessão

4.3 Testes de Diferentes Roles

 E2E: Fluxo de Admin completo
 E2E: Fluxo de Physician completo
 E2E: Fluxo de Pharmacist completo
 E2E: Fluxo de ReadOnly (apenas visualização)

4.4 Testes de Cenários de Erro

 E2E: Sessão expirada
 E2E: Permissão negada
 E2E: Arquivo inválido no upload
 E2E: Network error handling
 E2E: Timeout de análise

4.5 Integração CI/CD

 Adicionar job de E2E no GitHub Actions
 Configurar paralelização de testes
 Configurar retry de testes flaky
 Upload de artifacts (screenshots, vídeos)
 Integração com relatórios de teste


🟡 5. Melhorar Rate Limiting (User-based)
Esforço: 6-8 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex, Opus 4.5
Tarefas:

 Instalar e configurar Redis para rate limiting
 Modificar key function para priorizar user_id
 Implementar fallback para IP quando não autenticado
 Configurar limites diferentes por role
 Configurar limites diferentes por endpoint
 Usar estratégia moving-window (mais justa)
 Adicionar headers de rate limit nas respostas
 Criar dashboard de rate limiting no Grafana
 Testar com múltiplos usuários
 Documentar limites por endpoint

Limites sugeridos por endpoint:

 Login: 5/min por usuário (prevenção brute force)
 Triage: 10/min por usuário
 Vision analyze: 5/min por usuário
 Document search: 20/min por usuário
 General API: 100/min, 1000/hora por usuário


🟡 6. Adicionar Proteção Brute Force no Login
Esforço: 8-10 horas | Impaco: MÉDIO
Fonte: Opus 4.5
Tarefas:
6.1 Sistema de Lockout

 Implementar contador de tentativas falhas no Redis
 Configurar lockout após 5 tentativas
 Definir duração de lockout (30 minutos)
 Implementar janela de tempo (15 minutos)
 Reset automático de tentativas após login bem-sucedido
 Log de segurança para tentativas suspeitas

6.2 Backoff Exponencial

 Implementar delay crescente entre tentativas
 1ª tentativa falha: sem delay
 2ª tentativa: 2 segundos
 3ª tentativa: 5 segundos
 4ª tentativa: 10 segundos
 5ª tentativa: 30 segundos
 6+ tentativas: lockout completo

6.3 CAPTCHA para Casos Extremos

 Integrar Google reCAPTCHA v3
 Solicitar CAPTCHA nas últimas 2 tentativas
 Solicitar CAPTCHA após lockout
 Configurar threshold de score (≥0.5)
 Testar com bots e usuários reais

6.4 Notificações de Segurança

 Enviar email após lockout
 Notificar após múltiplas tentativas de IPs diferentes
 Dashboard de tentativas de login no admin
 Alertas para padrões suspeitos


🟡 7. Endurecer CI/CD Pipeline
Esforço: 8-10 horas | Impacto: MÉDIO
Fonte: Opus 4.5
Tarefas:
7.1 Remover continue-on-error

 Remover de ruff/flake8 (linting deve bloquear)
 Remover de mypy (type errors devem bloquear)
 Remover de bandit (security issues devem bloquear)
 Remover de safety (vulnerable deps devem bloquear)
 Configurar fail-fast em todos os jobs

7.2 Adicionar Secret Scanning

 Integrar TruffleHog no CI
 Configurar GitHub Secret Scanning
 Adicionar pre-commit hook para secrets
 Criar whitelist de false positives
 Documentar processo de rotação de secrets

7.3 Adicionar SAST (Static Analysis)

 Integrar GitHub CodeQL
 Configurar análise para Python e JavaScript
 Definir threshold de severidade
 Criar workflow de remediation
 Integração com GitHub Security tab

7.4 Melhorar Dependency Scanning

 Adicionar OWASP Dependency Check
 Configurar Dependabot alerts
 Criar política de atualização de dependências
 Automatizar PRs de security patches
 Monitorar CVEs de bibliotecas críticas

7.5 Adicionar Container Scanning

 Configurar Trivy com severidades CRITICAL, HIGH, MEDIUM
 Bloquear build com vulnerabilidades CRITICAL
 Criar workflow de remediation
 Scan de base images
 Integrar com GitHub Security

7.6 Smoke Tests Automatizados

 Teste de healthcheck endpoint
 Teste de docs/OpenAPI
 Teste de metrics endpoint
 Teste de conectividade com DB
 Teste de conectividade com Redis
 Teste de conectividade com Ollama
 Adicionar timeout de 60s para smoke tests


🟡 8. Implementar Migration Checks no CI
Esforço: 4-6 horas | Impacto: MÉDIO
Fonte: Opus 4.5
Tarefas:

 Criar workflow de verificação de migrations
 Verificar se migrations estão em sync com models
 Detectar migrations não commitadas
 Verificar ordem de migrations
 Testar migrations up/down
 Verificar integridade referencial
 Testar migrations em banco limpo
 Testar migrations com dados existentes
 Documentar processo de criação de migrations
 Criar checklist de PR para migrations


🟡 9. Corrigir Bug de Report Persistence
Esforço: 6-8 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex, Texto 1
Problema identificado:

Relatórios não estão sendo persistidos corretamente no banco
Dados perdidos após workflow

Tarefas:

 Investigar onde a persistência falha no workflow
 Verificar se é problema de commit de transação
 Verificar se é problema de estado do LangGraph
 Corrigir salvamento no HITLAgent
 Corrigir salvamento no final do workflow
 Adicionar logging de persistência
 Criar testes de persistência de reports
 Testar com workflow completo
 Validar integridade dos dados salvos
 Documentar ciclo de vida do report


🟡 10. Melhorar CORS por Ambiente
Esforço: 2-3 horas | Impacto: MÉDIO
Fonte: Opus 4.5
Problema identificado:

CORS padrão permite localhost:9000
Sem perfis separados por ambiente
Risco de má configuração em produção

Tarefas:

 Criar configuração CORS por ambiente (.env)
 Development: permitir localhost e IPs locais
 Staging: permitir apenas domínio de staging
 Production: permitir apenas domínios específicos
 Validar que wildcard não pode ser usado em produção
 Adicionar validação no Settings
 Testar CORS em cada ambiente
 Documentar configuração por ambiente
 Adicionar headers CORS corretos
 Testar preflight requests (OPTIONS)


📊 Resumo Fase 1
ItemEsforçoImpactoDependênciasMelhorar JWT8-12h🟡 ALTOFase 0 #1Endpoints Legacy V16-8h🟡 ALTO-Cobertura de Testes 80%+20-30h🟡 ALTOFase 0 #2Testes E2E12-16h🟡 ALTO-Rate Limiting User-based6-8h🟡 MÉDIO-Proteção Brute Force8-10h🟡 MÉDIORate LimitingEndurecer CI/CD8-10h🟡 MÉDIO-Migration Checks4-6h🟡 MÉDIO-Report Persistence Bug6-8h🟡 ALTO-CORS por Ambiente2-3h🟡 MÉDIO-
Total Fase 1: 80-120 horas

🟠 Fase 2: Médio Prazo (1 mês)
Prazo: 4 semanas
Esforço Total: 120-180 horas
Status: 🟠 MÉDIA PRIORIDADE
🟠 1. Migrar VisionAgent de AG2 para LangGraph
Esforço: 16-20 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex, Texto 1
Tarefas:

 Analisar código atual do VisionAgent (AG2 legacy)
 Desenhar nova arquitetura LangGraph
 Criar VisionAgent seguindo padrão BaseAgent
 Implementar state management para vision data
 Integrar com Qwen2.5-VL model
 Implementar fallback para Tesseract OCR
 Adicionar ao grafo principal do LangGraph
 Criar testes unitários do VisionAgent
 Criar testes de integração com workflow
 Testar com diferentes tipos de prescrições
 Validar performance (tempo de processamento)
 Deprecar código AG2 antigo
 Atualizar documentação
 Comunicar mudança aos usuários


🟠 2. Implementar Secrets Management Profissional
Esforço: 12-16 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex, Opus 4.5
Problema atual:

Secrets em variáveis de ambiente
Sem rotação automática
Sem auditoria de acesso

Opção A: AWS Secrets Manager

 Criar conta e configurar AWS Secrets Manager
 Migrar secrets para AWS Secrets Manager
 Implementar cliente de acesso aos secrets
 Configurar IAM roles e policies
 Implementar cache de secrets (TTL)
 Configurar rotação automática
 Implementar auditoria via CloudTrail
 Testar em staging e produção

Opção B: HashiCorp Vault

 Instalar e configurar Vault
 Configurar políticas de acesso
 Migrar secrets para Vault
 Implementar cliente de acesso
 Configurar dynamic secrets
 Configurar rotação automática
 Implementar auditoria
 Criar runbook de operação

Opção C: Kubernetes Secrets (se em K8s)

 Configurar External Secrets Operator
 Integrar com AWS/Azure/GCP Secrets
 Migrar secrets para formato K8s
 Configurar RBAC para secrets
 Implementar sealed secrets
 Configurar rotação
 Auditoria via K8s audit logs

Recomendação: Opção A (AWS) para cloud, Opção B (Vault) para on-premise

🟠 3. Automatizar Deploy Pipeline Completamente
Esforço: 16-24 horas | Impacto: ALTO
Fonte: Opus 4.5, GPT 5.1 Codex
Problema atual:

Deploy SSH comentado (não funcional)
Deploy manual necessário
Sem blue-green ou canary

Tarefas:
3.1 Deploy Staging Automatizado

 Configurar SSH keys no GitHub Secrets
 Implementar deploy via SSH ou API
 Configurar health checks pós-deploy
 Implementar rollback automático em falha
 Configurar notificações de deploy (Slack/Email)
 Criar logs de deploy estruturados
 Testar deploy em staging

3.2 Deploy Production com Aprovação

 Configurar aprovação manual obrigatória
 Implementar deploy blue-green ou canary
 Configurar smoke tests pós-deploy
 Implementar monitoramento pós-deploy (15min)
 Configurar rollback automático se métricas degradarem
 Criar runbook de rollback manual
 Documentar processo de deploy

3.3 Infraestrutura como Código

 Criar Terraform/CloudFormation templates
 Versionarinfra no Git
 Configurar apply automático em staging
 Configurar approval para apply em production
 Implementar drift detection
 Documentar arquitetura de infraestrutura

3.4 Database Migrations no Deploy

 Integrar Alembic migrations no pipeline
 Executar migrations antes do deploy
 Criar backup automático antes de migrations
 Implementar rollback de migrations
 Testar migrations em staging primeiro
 Adicionar smoke test pós-migration


🟠 4. Implementar Testes de Carga (Load Testing)
Esforço: 12-16 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex, Opus 4.5
Tarefas:
4.1 Setup de Load Testing

 Escolher ferramenta (Locust, K6, JMeter)
 Configurar ambiente de testes isolado
 Criar cenários realistas de uso
 Definir métricas de sucesso
 Configurar monitoramento durante testes

4.2 Cenários de Teste

 Teste de carga normal (100 usuários simultâneos)
 Teste de pico (500 usuários simultâneos)
 Teste de stress (até breaking point)
 Teste de endurance (24 horas contínuo)
 Teste de spike (crescimento súbito)
 Teste de recuperação após falha

4.3 Endpoints Críticos para Testar

 Login e autenticação
 Criação de triagem
 Análise de contraindicações
 RAG/busca de documentos
 Upload de arquivos
 Geração de relatórios

4.4 Métricas para Monitorar

 Response time (p50, p95, p99)
 Throughput (req/s)
 Error rate
 CPU e memória
 Database connections
 Cache hit rate
 LLM inference time

4.5 Análise e Otimização

 Identificar bottlenecks
 Documentar limites de capacidade
 Criar plano de otimização
 Implementar melhorias
 Re-testar após otimizações
 Documentar capacity planning


🟠 5. Melhorar Observabilidade (OpenTelemetry Completo)
Esforço: 16-20 horas | Impacto: MÉDIO
Fonte: Opus 4.5
Problema atual:

OTel libs declaradas mas não inicializadas
Apenas logging estruturado implementado
Sem traces distribuídas
Sem métricas customizadas suficientes

Tarefas:
5.1 Instrumentação OpenTelemetry

 Inicializar OpenTelemetry SDK
 Configurar exporters (Jaeger/Tempo para traces)
 Instrumentar FastAPI automaticamente
 Instrumentar SQLAlchemy
 Instrumentar Redis
 Instrumentar LLM calls (Ollama)
 Adicionar context propagation

5.2 Distributed Tracing

 Configurar trace IDs únicos por request
 Propagate trace context entre serviços
 Trace completo do workflow LangGraph
 Trace de cada agente separadamente
 Adicionar spans customizados
 Configurar sampling (100% em dev, 10% em prod)

5.3 Métricas Customizadas

 Métricas de negócio (triagens/dia, relatórios gerados)
 Métricas de agentes (tempo por agente, taxa de erro)
 Métricas de LLM (tokens, custo, latência)
 Métricas de HITL (tempo em fila, taxa de aprovação)
 Métricas de cache (hit rate, size)
 Métricas de database (query time, pool usage)

5.4 Dashboards Avançados

 Dashboard de overview geral (RED metrics)
 Dashboard de workflow LangGraph
 Dashboard de performance por agente
 Dashboard de custos (LLM, infra)
 Dashboard de HITL
 Dashboard de erros e alerts

5.5 Alerting

 Configurar alertas para error rate >1%
 Alertas para latência p99 >5s
 Alertas para CPU >80%
 Alertas para memória >85%
 Alertas para disk >90%
 Alertas para fila HITL >10 itens
 Integrar com PagerDuty ou OpsGenie


🟠 6. Implementar Query Result Caching
Esforço: 8-12 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex
Tarefas:

 Configurar Redis para cache de queries
 Implementar cache decorator para funções
 Definir TTL por tipo de query
 Cachear buscas de medicamentos (TTL: 24h)
 Cachear RAG queries comuns (TTL: 1h)
 Cachear resultados de interações (TTL: 24h)
 Implementar cache invalidation strategy
 Configurar cache warming para queries populares
 Adicionar métricas de cache hit rate
 Testar performance com e sem cache
 Documentar estratégia de caching


🟠 7. Configurar Database Connection Pooling
Esforço: 4-6 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex
Tarefas:

 Configurar pool size adequado (20-50 connections)
 Configurar max overflow (10-20)
 Configurar pool timeout (30s)
 Configurar pool pre-ping (verificar conexões válidas)
 Implementar retry logic para conexões
 Configurar pool recycle (1 hora)
 Adicionar métricas de pool usage
 Configurar alarmes para pool exhaustion
 Testar com load testing
 Documentar configuração de pool


🟠 8. Otimizar Queries do Database (N+1 Prevention)
Esforço: 12-16 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex
Tarefas:
8.1 Identificar N+1 Queries

 Habilitar query logging em desenvolvimento
 Analisar logs de queries por endpoint
 Identificar padrões de N+1
 Documentar queries problemáticas

8.2 Implementar Eager Loading

 Usar joinedload() para relacionamentos
 Usar selectinload() quando apropriado
 Usar subqueryload() para collections grandes
 Refatorar queries de triagem
 Refatorar queries de relatórios
 Refatorar queries de usuários

8.3 Adicionar Índices Faltantes

 Analisar slow query log
 Identificar queries sem índices adequados
 Criar migrations para novos índices
 Testar impacto de índices
 Monitorar uso de índices
 Remover índices não utilizados

8.4 Query Optimization

 Usar select específicos ao invés de SELECT *
 Adicionar limit() em queries grandes
 Usar defer() para colunas grandes
 Implementar pagination adequada
 Cache de queries repetidas
 Testar performance antes/depois


🟠 9. Adicionar Encryption at Rest para Dados Sensíveis
Esforço: 12-16 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex
Tarefas:
9.1 Identificar Dados Sensíveis

 Mapear todos os campos sensíveis (PII, PHI)
 Classificar por nível de sensibilidade
 Documentar requisitos legais (LGPD, HIPAA)
 Criar matriz de classificação de dados

9.2 Database Encryption

 Habilitar encryption at rest no PostgreSQL
 Configurar TDE (Transparent Data Encryption)
 Ou usar pgcrypto para colunas específicas
 Gerenciar keys de encryption
 Implementar key rotation
 Testar performance de encryption

9.3 Application-Level Encryption

 Implementar Fernet encryption para campos sensíveis
 Encriptar CPF/RG antes de salvar
 Encriptar dados de saúde (alergias, condições)
 Encriptar histórico de medicamentos
 Implementar key management
 Adicionar decrypt on read

9.4 Backup Encryption

 Encriptar backups do database
 Encriptar arquivos de upload
 Configurar encryption de snapshots
 Testar restore de backups encriptados
 Documentar procedimento de recovery


🟠 10. Sanitização de Logs (Remover Informações Sensíveis)
Esforço: 6-8 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex
Tarefas:

 Identificar informações sensíveis em logs
 Implementar log sanitizer
 Maskear CPF/RG (XXX.XXX.XXX-XX)
 Maskear emails (u***@domain.com)
 Remover tokens JWT completos
 Remover senhas e API keys
 Sanitizar dados de saúde (doenças, medicamentos)
 Configurar níveis de log por ambiente
 Testar sanitização em todos os logs
 Documentar política de logging


📊 Resumo Fase 2
ItemEsforçoImpactoComplexidadeMigrar VisionAgent16-20h🟠 MÉDIO🔴 AltaSecrets Management12-16h🟠 ALTO🟡 MédiaAutomatizar Deploy16-24h🟠 ALTO🔴 AltaLoad Testing12-16h🟠 MÉDIO🟡 MédiaOpenTelemetry Completo16-20h🟠 MÉDIO🔴 AltaQuery Caching8-12h🟠 MÉDIO🟢 BaixaConnection Pooling4-6h🟠 MÉDIO🟢 BaixaOtimizar Queries12-16h🟠 MÉDIO🟡 MédiaEncryption at Rest12-16h🟠 ALTO🟡 MédiaSanitização de Logs6-8h🟠 MÉDIO🟢 Baixa
Total Fase 2: 114-174 horas

🟢 Fase 3: Longo Prazo (3+ meses)
Prazo: 12-16 semanas
Esforço Total: 200-300+ horas
Status: 🟢 BAIXA PRIORIDADE / MELHORIAS FUTURAS
🟢 1. Integração com Cloud LLM (Fallback/Alternativa)
Esforço: 20-30 horas | Impacto: MÉDIO
Fonte: GPT 5.1 Codex, Texto 2, Texto 4
Motivação:

Ollama local pode ser gargalo
Custos de infra para GPU podem ser altos
Fallback quando Ollama indisponível

Tarefas:
1.1 Abstração de LLM Provider

 Criar interface abstrata de LLM
 Implementar OllamaProvider (existente)
 Implementar OpenAIProvider
 Implementar AnthropicProvider (Claude)
 Implementar GoogleProvider (Gemini)
 Configurar fallback chain
 Implementar cost tracking por provider

1.2 Configuração Multi-Provider

 Adicionar configuração de providers no .env
 Implementar seleção de provider por uso
 Configurar fallback automático
 Implementar load balancing entre providers
 Configurar limites de custo por provider
 Dashboard de uso por provider

1.3 Testing e Validação

 Testar todos os providers
 Comparar qualidade de outputs
 Comparar latência
 Comparar custos
 Testar fallback automático
 Documentar trade-offs


🟢 2. Migração para Arquitetura de Microservices
Esforço: 80-120 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex
Motivação:

Escalabilidade independente de componentes
Isolamento de falhas
Deploy independente
Otimização de recursos

Tarefas:
2.1 Planejamento

 Identificar bounded contexts
 Desenhar arquitetura de microservices
 Definir comunicação entre serviços (REST/gRPC/MessageQueue)
 Planejar migração gradual
 Documentar arquitetura target

2.2 Serviços Propostos

 Auth Service: Autenticação, JWT, RBAC
 Triage Service: Gestão de triagens
 Analysis Service: LangGraph workflow e agentes
 Document Service: RAG, vector search, embeddings
 Report Service: Geração e gestão de relatórios
 Notification Service: Emails, webhooks, alertas
 HITL Service: Fila de aprovações, workflow humano

2.3 Infraestrutura

 Configurar API Gateway (Kong, Traefik)
 Implementar service discovery (Consul, Eureka)
 Configurar message broker (RabbitMQ, Kafka)
 Implementar circuit breakers (Hystrix, Resilience4j)
 Configurar distributed tracing
 Implementar service mesh (Istio, Linkerd) - opcional

2.4 Database per Service

 Separar schemas por serviço
 Ou usar databases separados
 Implementar event sourcing para sincronização
 Configurar CDC (Change Data Capture) se necessário
 Gerenciar transações distribuídas (Saga pattern)

2.5 Deploy e Orquestração

 Migrar para Kubernetes (K8s)
 Configurar Helm charts por serviço
 Implementar auto-scaling por serviço
 Configurar health checks
 Implementar rolling updates
 Configurar canary deployments


🟢 3. Migração para Kubernetes
Esforço: 40-60 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex
Tarefas:
3.1 Setup de Cluster

 Provisionar cluster K8s (EKS, GKE, AKS, ou self-hosted)
 Configurar networking (CNI)
 Configurar storage classes
 Configurar ingress controller (Nginx, Traefik)
 Configurar cert-manager para SSL

3.2 Containerização

 Otimizar Dockerfiles para K8s
 Multi-stage builds
 Distroless images para segurança
 Configurar registry privado

3.3 Kubernetes Resources

 Criar Deployments para cada serviço
 Configurar Services (ClusterIP, NodePort)
 Criar ConfigMaps e Secrets
 Configurar PersistentVolumeClaims
 Implementar HorizontalPodAutoscaler
 Configurar PodDisruptionBudgets
 Implementar NetworkPolicies

3.4 Helm Charts

 Criar Helm chart para MedSafe
 Parametrizar por ambiente (dev, staging, prod)
 Configurar values.yaml
 Testar deploy com Helm
 Versionamento de charts

3.5 Observabilidade em K8s

 Deploy Prometheus Operator
 Deploy Grafana
 Configurar Loki para logs
 Configurar Jaeger para traces
 Dashboards de métricas de cluster
 Alerting com AlertManager

3.6 CI/CD para K8s

 Integrar kubectl no pipeline
 Ou usar Helm no pipeline
 Configurar GitOps com ArgoCD/Flux
 Implementar canary deployments
 Configurar rollback automático


🟢 4. Suporte Multi-região
Esforço: 60-90 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex
Motivação:

Reduzir latência para usuários globais
Alta disponibilidade
Compliance regulatório (dados no país)

Tarefas:
4.1 Arquitetura Multi-região

 Definir regiões (BR-South, US-East, EU-West)
 Desenhar topologia de rede
 Planejar replicação de dados
 Decidir active-active vs active-passive

4.2 Database Replication

 Configurar PostgreSQL replication
 Ou usar database gerenciado com multi-region (Aurora Global)
 Configurar read replicas por região
 Implementar conflict resolution
 Testar failover entre regiões

4.3 Load Balancing Global

 Configurar DNS-based routing (Route53, CloudFlare)
 Implementar health checks por região
 Configurar latency-based routing
 Ou geo-proximity routing
 Configurar failover automático

4.4 Cache e CDN

 Configurar Redis Cluster multi-região
 Ou usar ElastiCache Global Datastore
 Configurar CDN (CloudFront, CloudFlare)
 Cache de assets estáticos
 Cache de API responses quando possível

4.5 Compliance e Data Residency

 Garantir que dados BR fiquem no Brasil (LGPD)
 Configurar encryption em trânsito entre regiões
 Implementar data classification
 Auditar fluxo de dados entre regiões
 Documentar conformidade


🟢 5. Dashboard de Analytics Avançado
Esforço: 30-40 horas | Impacto: BAIXO
Fonte: GPT 5.1 Codex
Tarefas:
5.1 Métricas de Negócio

 Dashboard de KPIs principais
 Triagens por dia/semana/mês
 Relatórios gerados
 Taxa de detecção de contraindicações
 Medicamentos mais analisados
 Interações mais frequentes
 Taxa de aprovação HITL
 Tempo médio de análise

5.2 Analytics de Usuários

 Usuários ativos (DAU, MAU)
 Distribuição por role
 Sessões por usuário
 Tempo médio de sessão
 Features mais utilizadas
 Jornada do usuário (funnel)

5.3 Analytics de Performance

 Latência por endpoint (p50, p95, p99)
 Throughput (req/s)
 Error rate por endpoint
 Performance de agentes LangGraph
 Custo por análise
 Cache hit rate

5.4 Business Intelligence

 Integrar com Metabase ou Superset
 Criar data warehouse (Redshift, BigQuery)
 Implementar ETL pipeline
 Criar dashboards executivos
 Relatórios agendados


🟢 6. Minificação e Bundling do Frontend
Esforço: 8-12 horas | Impacto: BAIXO
Fonte: Texto 2
Tarefas:

 Configurar Webpack ou Vite
 Minificar JavaScript
 Minificar CSS
 Otimizar imagens
 Implementar code splitting
 Configurar lazy loading
 Implementar tree shaking
 Gzip/Brotli compression
 Configurar cache headers adequados
 Testar performance com Lighthouse
 Medir impacto em First Contentful Paint


🟢 7. Separar Frontend em Projeto Independente
Esforço: 40-60 horas | Impacto: MÉDIO
Fonte: Texto 4, Texto 2
Motivação:

Escalabilidade de UI/UX
Deploy independente
Framework moderno (React/Vue/Next.js)

Tarefas:
7.1 Setup de Novo Projeto

 Escolher framework (React, Vue, ou Next.js)
 Configurar projeto com TypeScript
 Configurar linting e formatação
 Configurar testes (Jest, Vitest)
 Configurar CI/CD

7.2 Migração de Features

 Reescrever autenticação e login
 Reescrever formulário de triagem
 Reescrever upload de arquivos
 Reescrever visualização de relatórios
 Reescrever busca de medicamentos
 Reescrever dashboard
 Reescrever fila HITL
 Migrar visualização 3D (Three.js)

7.3 State Management

 Configurar Redux/Zustand/Pinia
 Implementar autenticação state
 Implementar user state
 Implementar triage state
 Persistência de state (localStorage)

7.4 API Client

 Criar cliente HTTP (Axios/Fetch)
 Implementar interceptors
 Implementar retry logic
 Implementar cache de requests
 Type-safe API com geração de tipos

7.5 UI/UX Melhorado

 Design system (Material UI, Ant Design, Chakra UI)
 Componentes reutilizáveis
 Responsividade completa
 Acessibilidade (WCAG 2.1)
 Dark mode
 Animações e transições


🟢 8. Implementar WebSockets para Updates Real-time
Esforço: 16-24 horas | Impacto: BAIXO
Fonte: Texto 2
Tarefas:

 Adicionar suporte WebSocket no FastAPI
 Implementar connection manager
 Autenticação de WebSocket connections
 Real-time updates de status de análise
 Real-time notifications para HITL
 Real-time updates de fila de aprovação
 Fallback para polling quando WS não disponível
 Testar reconexão automática
 Testar com múltiplos clientes simultâneos
 Monitorar conexões abertas


🟢 9. Suporte a Múltiplos Idiomas (i18n)
Esforço: 20-30 horas | Impacto: BAIXO
Fonte: Texto 2
Tarefas:
9.1 Backend i18n

 Implementar Accept-Language parsing
 Criar sistema de traduções
 Traduzir mensagens de erro
 Traduzir mensagens de validação
 Traduzir emails e notificações
 Traduzir relatórios gerados

9.2 Frontend i18n

 Configurar i18next ou vue-i18n
 Criar arquivos de tradução (pt-BR, en-US, es-ES)
 Traduzir toda a UI
 Implementar language selector
 Persistir preferência de idioma
 Formato de datas por locale
 Formato de números por locale

9.3 Database i18n

 Decidir estratégia (tabelas separadas vs JSON columns)
 Migrar conteúdo existente
 Implementar fallback para idioma padrão


🟢 10. Adicionar Mais Idiomas no OCR
Esforço: 8-12 horas | Impacto: BAIXO
Fonte: Texto 2
Tarefas:

 Instalar language packs do Tesseract
 Adicionar suporte a inglês (eng)
 Adicionar suporte a espanhol (spa)
 Configurar detecção automática de idioma
 Treinar modelo para terminologia médica
 Testar accuracy por idioma
 Documentar suporte de idiomas


🟢 11. Implementar Feature Flags
Esforço: 12-16 horas | Impacto: MÉDIO
Fonte: Inferido (best practice)
Tarefas:

 Escolher plataforma (LaunchDarkly, Unleash, self-hosted)
 Implementar client de feature flags
 Criar flags para features experimentais
 Implementar A/B testing
 Configurar rollout gradual de features
 Configurar kill switches para emergências
 Dashboard de feature flags
 Integrar com analytics


🟢 12. Implementar Auditoria Completa (LGPD Compliance)
Esforço: 24-32 horas | Impacto: ALTO
Fonte: GPT 5.1 Codex
Tarefas:
12.1 Audit Log Completo

 Criar tabela de audit log
 Logar todas as ações do usuário
 Logar criação, edição, remoção de dados
 Logar acessos a dados sensíveis
 Logar mudanças de permissões
 Incluir IP, user-agent, timestamp
 Implementar retenção de logs (7 anos)

12.2 Direitos do Titular (LGPD)

 Implementar endpoint de "Acessar meus dados"
 Implementar endpoint de "Corrigir meus dados"
 Implementar endpoint de "Deletar meus dados" (right to be forgotten)
 Implementar endpoint de "Portabilidade de dados" (export JSON/CSV)
 Implementar consentimento explícito para coleta
 Implementar opt-out de processamento
 Documentar base legal para cada processamento

12.3 Anonimização

 Implementar anonimização de dados antigos
 Pseudonimização para analytics
 Remover identificadores diretos
 Documentar processo de anonimização

12.4 Data Protection Officer (DPO)

 Designar DPO
 Criar canal de comunicação com DPO
 Documentar processos de privacidade
 Treinar equipe em LGPD


📊 Resumo Fase 3
ItemEsforçoImpactoROICloud LLM Integration20-30h🟢 MÉDIO🟡 MédioMicroservices80-120h🟢 ALTO🟢 AltoKubernetes40-60h🟢 ALTO🟢 AltoMulti-região60-90h🟢 ALTO🟡 MédioAnalytics Dashboard30-40h🟢 BAIXO🟢 AltoFrontend Bundling8-12h🟢 BAIXO🟡 MédioFrontend Separado40-60h🟢 MÉDIO🟡 MédioWebSockets16-24h🟢 BAIXO🟢 Altoi18n (Internacionalização)20-30h🟢 BAIXO🔴 BaixoOCR Multi-idioma8-12h🟢 BAIXO🔴 BaixoFeature Flags12-16h🟢 MÉDIO🟢 AltoLGPD Compliance24-32h🟢 ALTO🟢 Alto
Total Fase 3: 358-536 horas (~3-6 meses com equipe de 2-3 devs)

📊 Resumo Executivo de Esforço e Impacto
Por Fase
FasePrazoEsforço Total# ItensStatusFase 03-5 dias40-60h6⛔ BLOQUEADORFase 11-2 semanas80-120h10🟡 ALTA PRIORIDADEFase 21 mês114-174h10🟠 MÉDIA PRIORIDADEFase 33-6 meses358-536h12🟢 BAIXA PRIORIDADETOTAL4-7 meses592-890h38-
Por Categoria de Impacto
Impacto# ItensEsforço Total% do Total🔴 CRÍTICO640-60h7%🟡 ALTO13240-350h35%🟠 MÉDIO14240-360h38%🟢 BAIXO572-120h20%
Top 10 Itens por ROI (Return on Investment)
RankItemFaseEsforçoImpactoROI1Corrigir Refresh Token Bug04-6h🔴 CRÍTICO⭐⭐⭐⭐⭐2Implementar RBAC Real08-12h🔴 CRÍTICO⭐⭐⭐⭐⭐3Aplicar Security Headers02-3h🔴 CRÍTICO⭐⭐⭐⭐⭐4Aumentar Cobertura de Testes120-30h🟡 ALTO⭐⭐⭐⭐5Testes E2E112-16h🟡 ALTO⭐⭐⭐⭐6Melhorar JWT Security18-12h🟡 ALTO⭐⭐⭐⭐7Automatizar Deploy216-24h🟠 ALTO⭐⭐⭐⭐8LGPD Compliance324-32h🟢 ALTO⭐⭐⭐⭐9Feature Flags312-16h🟢 MÉDIO⭐⭐⭐⭐10Query Caching28-12h🟠 MÉDIO⭐⭐⭐

🎯 Recomendações de Execução

Estratégia de Implementação
Semana 1-2: FASE 0 COMPLETA

Foco total em bloqueadores críticos
Code freeze de features
2-3 desenvolvedores dedicados
Critério de sucesso: Todos os 6 itens completos e testados

Semana 3-4: FASE 1 (Parte 1)

Melhorar JWT + RBAC
Aumentar testes para 80%
Implementar testes E2E
Proteger endpoints legacy

Semana 5-6: FASE 1 (Parte 2)

Rate limiting melhorado
Proteção brute force
Endurecer CI/CD
Corrigir report persistence bug

Mês 2: FASE 2 (Alta Prioridade)

Secrets management
Automatizar deploy
Load testing
OpenTelemetry completo

Mês 2-3: FASE 2 (Restante)

Migrar VisionAgent
Otimizações de performance
Encryption e sanitização

Mês 4-7: FASE 3 (Conforme Necessidade)

Implementar baseado em prioridades de negócio
Microservices se escala for necessária
Multi-região se tiver usuários globais
LGPD compliance deve ser priorizado

Alocação de Recursos Sugerida
PapelFase 0Fase 1Fase 2Fase 3Backend Dev Senior100%80%60%40%Backend Dev Mid100%80%60%40%Frontend Dev-40%40%60%DevOps50%60%80%80%QA50%80%60%40%Security SpecialistConsultoriaConsultoriaConsultoria-
Checkpoints de Validação
Após Fase 0:

✅ Todos os testes de segurança passando
✅ Penetration test executado
✅ Aprovação de security specialist
✅ Code review completo
GO/NO-GO para produção

Após Fase 1:

✅ Cobertura de testes ≥ 80%
✅ E2E tests passando
✅ Load test com resultados satisfatórios
✅ Zero vulnerabilidades CRITICAL/HIGH

Após Fase 2:

✅ Deploy automatizado funcionando
✅ Observabilidade completa
✅ Performance melhorada (métricas)
✅ Documentação atualizada

Após Fase 3:

✅ Escalabilidade horizontal validada
✅ Multi-região testado (se aplicável)
✅ Compliance audit passando
✅ Satisfação de usuários >85%


📋 Templates de Tracking
Template de Issue/Task
markdown## [FASE X] [PRIORIDADE] Nome da Tarefa

**Esforço estimado:** Xh  
**Impacto:** CRÍTICO/ALTO/MÉDIO/BAIXO  
**Dependências:** #issue1, #issue2  
**Assignee:** @username

### Contexto
[Por que estamos fazendo isso]

### Tarefas
- [ ] Subtarefa 1
- [ ] Subtarefa 2
- [ ] Subtarefa 3

### Critérios de Aceitação
- [ ] Critério 1
- [ ] Critério 2
- [ ] Testes passando
- [ ] Code review aprovado
- [ ] Documentação atualizada

### Testes
- [ ] Testes unitários
- [ ] Testes de integração
- [ ] Testes E2E (se aplicável)

### Notas
[Informações adicionais]
Template de Release Notes
markdown# MedSafe v2.1.0 - Release Notes

**Data:** YYYY-MM-DD  
**Fase:** X

## 🚀 Novos Recursos
- Feature 1
- Feature 2

## 🔒 Segurança
- Security fix 1
- Security fix 2

## 🐛 Correções de Bugs
- Bug fix 1
- Bug fix 2

## ⚡ Melhorias de Performance
- Performance 1
- Performance 2

## 📚 Documentação
- Doc update 1

## ⚠️ Breaking Changes
- Breaking change 1

## 🔄 Migrations
```sql
-- Migration commands
```

## 📊 Métricas
- Cobertura de testes: XX%
- Vulnerabilidades: X CRITICAL, X HIGH
- Performance: X ms p95 (-Y% vs anterior)

🎓 Conclusão
Este roadmap consolida as análises de 4 especialistas diferentes e fornece um plano completo e acionável para levar o MedSafe de um estado "production-ready com ressalvas" para um sistema de classe mundial em segurança, performance e escalabilidade.
Prioridades imediatas (próximos 30 dias):

⛔ Completar Fase 0 (bloqueadores críticos)
🟡 Executar itens de alta prioridade da Fase 1
📊 Estabelecer métricas de sucesso e monitoramento

Compromisso com qualidade:

Cada item deve ter testes automatizados
Cada item deve ser revisado por pelo menos 2 pessoas
Cada item deve ter documentação atualizada
Nenhum item de FASE 0 pode ser pulado

Métricas de Sucesso do Roadmap:

🎯 100% dos itens de Fase 0 completos antes de produção
🎯 80%+ de cobertura de testes após Fase 1
🎯 Zero vulnerabilidades CRITICAL/HIGH após Fase 1
🎯 <2s p95 latency após Fase 2
🎯 99.9% uptime após Fase 2come