# Spec: Production Readiness — MedSafe

**Feature**: production-readiness
**Status**: Implementing

## Problem Statement

O MedSafe precisa ir a produção em stack de host único (docker-compose.prod.yml: api FastAPI, worker, postgres, redis, nginx, backup, grafana, prometheus). Antes do go-live é preciso provar, com evidência executável, que segurança (auth, segredos, sunset da v1), confiabilidade (health, HITL, degradação) e qualidade (suite backend, E2E público) atendem os critérios auditados.

## Assumptions & Open Questions

- A1: Stack roda em host único via docker compose (sem orquestrador externo). Confirmado pelo usuário.
- A2: Ollama roda no host (host.docker.internal:11434) e não é gerido pelo compose. Confirmado.
- A3: TLS terminado no nginx com certificado local (ambiente de homologação). Confirmado.
- Q1 (resolvida): Grafana/Prometheus ficam fora do gate bloqueante — tratados como melhoria.

Open questions: none

## User Stories

### P1: Operador sobe o stack de produção com segurança

Como operador, quero que o stack suba apenas com segredos vindos do ambiente e sem credencial default, para que um vazamento de imagem/repo não comprometa o banco nem o admin.

**Acceptance Criteria**: ver PROD-01, PROD-05.

### P1: Usuário final usa o fluxo público sem sessão

Como usuário anônimo, quero analisar interações na home e ser orientado a logar quando necessário, para que o produto funcione sem fricção e sem vazar erros técnicos.

**Acceptance Criteria**: ver PROD-02, PROD-03, PROD-04, PROD-07.

### P1: Farmacêutico revisa análises de alto risco

Como farmacêutico revisor, quero que análises de risco alto/crítico entrem obrigatoriamente na fila HITL, para que nenhum caso perigoso seja liberado sem revisão humana.

**Acceptance Criteria**: ver PROD-08.

## Requirements

### PROD-01: Autenticação rejeita credenciais inválidas

WHEN um POST /api/v2/auth/login é enviado com senha incorreta, THE SYSTEM SHALL responder HTTP 401 com mensagem genérica, sem stacktrace e sem revelar se o e-mail existe.

**Acceptance Criteria**:
- AC-01.1: WHEN login com senha errada THEN status 401 e corpo sem traceback.
- AC-01.2: WHEN login com e-mail inexistente THEN mesma resposta 401 genérica (sem enumeração de usuários).

### PROD-02: API v1 removida com sunset

WHEN qualquer rota /api/v1/* é chamada, THE SYSTEM SHALL responder HTTP 410 Gone com guia de migração para /api/v2.

**Acceptance Criteria**:
- AC-02.1: WHEN GET /api/v1/health THEN status 410 e corpo contém referência a /api/v2.

### PROD-03: Healthcheck estruturado

WHEN GET /api/v2/health é chamado, THE SYSTEM SHALL responder 200 com JSON contendo status, version e flags de features (hitl_workflow, jwt_authentication).

**Acceptance Criteria**:
- AC-03.1: WHEN GET /api/v2/health THEN 200 e campo status == "healthy".

### PROD-04: Vision exige sessão

WHEN POST /api/v2/vision/analyze é chamado sem token, THE SYSTEM SHALL responder 401, e o frontend SHALL exibir orientação de login.

**Acceptance Criteria**:
- AC-04.1: WHEN vision/analyze sem Authorization THEN 401.

### PROD-05: Segredos só via ambiente

WHEN os containers sobem, THE SYSTEM SHALL obter POSTGRES_PASSWORD, JWT_SECRET e ADMIN_INITIAL_PASSWORD exclusivamente de variáveis de ambiente/secret files, sem valores default embutidos em imagem ou logs.

**Acceptance Criteria**:
- AC-05.1: WHEN a configuração é carregada sem POSTGRES_PASSWORD THEN o startup falha explicitamente (sem fallback silencioso).
- AC-05.2: WHEN migração 008 roda THEN o hash default de admin é rotacionado a partir de ADMIN_INITIAL_PASSWORD.

### PROD-06: Suite backend com cobertura mínima

WHEN a suite pytest do backend roda, THE SYSTEM SHALL passar com 0 falhas e cobertura total ≥ 60%.

**Acceptance Criteria**:
- AC-06.1: WHEN pytest roda no backend THEN exit 0 e cobertura ≥ 60%.

### PROD-07: Fluxo público E2E íntegro

WHEN o fluxo público (home → step1 → step2 → modal auth → login inválido → upload anônimo → mobile 375px) roda via Playwright, THE SYSTEM SHALL completar sem erros de console não esperados e sem overflow horizontal em mobile.

**Acceptance Criteria**:
- AC-07.1: WHEN e2e.js roda THEN únicos 4xx são 401 esperados (login inválido, vision sem sessão) e overflow mobile == 0px.

### PROD-08: Gating de risco HITL

WHEN uma análise resulta em risco alto/crítico, THE SYSTEM SHALL marcar requires_human_review = true no estado do grafo.

**Acceptance Criteria**:
- AC-08.1: WHEN risk_level em {high, critical} THEN requires_human_review == true.
- AC-08.2: WHEN risk_level desconhecido/ausente THEN o sistema degrada para "unknown" sem crash (never-crash serialization).

## Edge Cases

- E1: risk_level None/valor inesperado na serialização → normaliza para "unknown", nunca lança.
- E2: nginx reiniciado após recreate da api (IP novo) → upstream volta a responder (resolver/restart documentado).
- E3: Redis indisponível → healthcheck reporta degradação sem derrubar a API.

## Out of Scope

- Orquestração multi-host, CDN, WAF externo.
- Grafana/Prometheus healthchecks (não-bloqueante, melhoria futura).

## Requirement Traceability

| Requirement | Status |
| ----------- | ------ |
| PROD-01 | Verified |
| PROD-02 | Verified |
| PROD-03 | Verified |
| PROD-04 | Verified |
| PROD-05 | Verified |
| PROD-06 | Verified |
| PROD-07 | Verified |
| PROD-08 | Verified |
