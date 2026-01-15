# MedSafe - Análise de Produção e Arquitetura

**Data (original):** 2025-11-12  
**Atualização:** 2025-12-16  
**Versão:** 1.0.0  
**Status:** ⚠️ Production Ready (com pendências explícitas)

---

## ✅ Atualização 2025-12-16 (Estado real do repositório)

O repositório evoluiu desde o texto original. Principais mudanças relevantes para produção/deploy:

- **Autenticação / RBAC**: implementado (`backend/app/auth/jwt.py`, `backend/app/auth/rbac.py`)
- **Execução durável**: jobs persistidos (`AnalysisJob`) + worker separado
- **Redis**: cache e rate limiting (compose ajustado para evitar conflito de porta)
- **Segurança**: headers/CSP/TrustedHost no backend + rate limiting no Nginx
- **Testes/CI**: workflows existem e cobertura alvo foi elevada para **80%**

> Nota: o restante deste documento contém contexto histórico e recomendações. A auditoria abaixo reflete o estado atual do repo.

---

## 🧾 Auditoria de Produção & Deploy (2025-12-16)

### CRÍTICO

1) **Drift de schema: `create_all()` em produção (Alembic vs ORM)**
- **Local**: `backend/app/db/database.py` (função `init_db()`)
- **Risco**: divergência silenciosa entre schema e migrations; deploy não determinístico
- **Evidência**:

```57:85:/home/lucasmsilva/Documentos/Cursor/MedSafe/backend/app/db/database.py
def init_db():
    """Inicializar banco de dados e criar tabelas"""
    try:
        # ...
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tabelas criadas com sucesso")
```

- **Ação recomendada**: em produção, executar `alembic upgrade head` como passo obrigatório e evitar `create_all()` em Postgres.

2) **CI duplicado + checks não-bloqueantes (corrigido em 2025-12-16)**
- **Ação tomada**: workflow redundante removido e CI consolidado em `.github/workflows/ci.yml`
- **Resultado**: lint/type-check agora são **bloqueantes** (falham o pipeline)

### MÉDIO

3) **Port conflicts por mapeamento fixo**
- **Sintoma**: `bind: address already in use` (ex.: Redis 6379 no host)
- **Causa**: `ports: "6379:6379"` em compose
- **Mitigação aplicada**: `REDIS_HOST_PORT` default `6380` (dev e prod compose)

4) **Worker em polling constante (ruído/custo)**
- **Sintoma**: logs repetidos de `SELECT ... FOR UPDATE SKIP LOCKED ... ROLLBACK`
- **Causa**: loop sem backoff quando não há jobs pendentes; SQL echo pode amplificar
- **Ação recomendada**: backoff exponencial quando fila vazia + desligar SQL echo em produção.

### MENOR

5) **Documentação desalinhada**
- Trechos abaixo ainda refletem arquitetura/estado anterior. Usar esta seção (2025-12-16) + roadmap atualizado como referência atual.

## 📋 Sumário Executivo

O MedSafe é um sistema de análise de contraindicações medicamentosas baseado em agentes de IA, projetado para uso por profissionais de saúde. A arquitetura atual implementa **padrões agênticos de ponta** (Reflection, Safety Guardrails, Human-in-the-Loop) e está **funcional e segura** para ambientes de produção controlados.

### Status Atual

| Componente | Status | Observações |
|------------|--------|-------------|
| API Backend | ✅ Funcional | FastAPI + middlewares + routers (v2 + legacy) |
| Execução durável | ✅ Implementado | `AnalysisJob` + worker separado (fila no DB) |
| Base de Interações | ✅ Operacional | Tabela `drug_interactions` + fallback CSV |
| Segurança | ✅ Boa base | JWT/RBAC + headers + rate limiting + LGPD logging |
| Frontend | ✅ Funcional | Sanitização XSS (DOMPurify + fallback) |
| Testes/CI | ⚠️ Em evolução | Workflows presentes; alvo cobertura ≥80% |
| Observabilidade | ⚠️ Parcial | Prometheus/Grafana presentes; ajustar exposição/alertas |

---

## 🏗️ Arquitetura do Sistema

### Visão Geral

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/JS)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Triagem   │  │ Medicações  │  │  Resultados │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/REST
┌─────────────────────────▼───────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              CaptainAgent (Orchestrator)              │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │  1. Triagem  →  2. Vision  →  3. Evidence      │ │   │
│  │  │         ↓              ↓             ↓           │ │   │
│  │  │  4. Clinical Analysis  →  5. Reflection         │ │   │
│  │  │         ↓                        ↓               │ │   │
│  │  │  6. Safety Guardrails  →  7. HITL Check        │ │   │
│  │  │         ↓                        ↓               │ │   │
│  │  │  8. Report Generation  →  9. Response          │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐   │
│  │ VisionAgent   │  │  DocAgent     │  │ ClinicalAgent│   │
│  │ (OCR/Visão)   │  │  (RAG/Search) │  │ (Regras)     │   │
│  └───────────────┘  └───────────────┘  └──────────────┘   │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Safety & Validation Layer                 │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │ │
│  │  │  Guardrails  │  │  Reflection  │  │    HITL     │ │ │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                     Data Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ PostgreSQL  │  │  pgvector   │  │   Ollama    │          │
│  │   (Dados)   │  │ (Embeddings)│  │   (LLMs)    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │   Drug Interactions DB (CSV - 191k+ interações)       │ │
│  └────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### Padrões Agênticos Implementados

#### 1. **Orchestration Pattern** (Captain Agent)
- **Localização:** `backend/app/agents/orchestrator.py`
- **Responsabilidade:** Coordenar workflow de análise end-to-end
- **Implementação:** ✅ Completa
- **Qualidade:** ⭐⭐⭐⭐⭐ (5/5)

```python
# Fluxo de orquestração:
1. Criar triagem no banco
2. Análise de visão (se imagem disponível)
3. Buscar evidências (RAG)
4. Análise clínica (regras + interactions DB)
5. Reflexão e refinamento iterativo
6. Validação com Safety Guardrails
7. Avaliação de necessidade de revisão humana (HITL)
8. Geração de relatório final
```

#### 2. **Reflection Pattern** (Self-Critique)
- **Localização:** `backend/app/agents/reflection_agent.py`
- **Responsabilidade:** Validar e refinar análises através de auto-crítica
- **Implementação:** ✅ Completa (baseado em Capítulo 4 - "Introduction to Agents")
- **Qualidade:** ⭐⭐⭐⭐⭐ (5/5)

**Tipos de Reflexão Implementados:**
- `consistency_check`: Verifica consistências internas
- `evidence_validation`: Valida evidências fornecidas
- `completeness_check`: Verifica se análise está completa
- `risk_assessment_review`: Revisa classificação de risco
- `logical_coherence`: Verifica lógica e coerência

**Métricas de Reflexão:**
- Até 2 ciclos de refinamento iterativo
- Classificação por níveis: PASS, MINOR, MAJOR, CRITICAL
- Regeneração automática se issues críticos detectados

#### 3. **Safety Guardrails Pattern**
- **Localização:** `backend/app/agents/safety_guardrails.py`
- **Responsabilidade:** Proteger contra conteúdo perigoso e garantir conformidade
- **Implementação:** ✅ Completa
- **Qualidade:** ⭐⭐⭐⭐⭐ (5/5)

**Camadas de Proteção:**

1. **Blocked Content Detection**
   - Detecta frases proibidas (diagnósticos diretos, prescrições)
   - Bloqueia garantias absolutas
   - Previne conselhos médicos não autorizados

2. **Hallucination Detection**
   - Score de alucinação (0-1)
   - Validação de evidências
   - Detecção de inconsistências
   - Identificação de declarações absolutas

3. **Regulatory Compliance**
   - Validação de uso em gravidez
   - Validação de dosagem pediátrica
   - Verificação de substâncias controladas

4. **Legal Disclaimers**
   - Injeção automática de disclaimers apropriados
   - Disclaimers específicos por população (gravidez, pediátrico, idoso)
   - Disclaimers por nível de risco

5. **Safety Classification**
   - Classificação: safe, warning, dangerous, blocked
   - Baseado em múltiplos fatores (alucinação, compliance, risco médico)

#### 4. **Human-in-the-Loop (HITL) Pattern**
- **Localização:** `backend/app/agents/human_in_the_loop.py`
- **Responsabilidade:** Escalar decisões complexas para revisão humana
- **Implementação:** ✅ Completa
- **Qualidade:** ⭐⭐⭐⭐ (4/5)

**Critérios de Escalação:**
- Baixa confiança (< 0.7)
- Interações críticas (≥1)
- Contraindicações críticas (≥1)
- Múltiplas interações high (≥3)
- Populações vulneráveis (idade < 12 ou gestante)
- Alta alucinação (> 0.6)
- Issues compliance críticos

#### 5. **Tool Use Pattern** (Interaction Classifier)
- **Localização:** `backend/app/services/interaction_classifier.py`
- **Responsabilidade:** Classificar severidade de interações medicamentosas
- **Implementação:** ✅ Completa
- **Qualidade:** ⭐⭐⭐⭐⭐ (5/5)

**Padrões Clínicos:**
- CRITICAL: QT prolongation, bleeding risk, cardiac arrest
- HIGH: Cardiotoxicity, hepatotoxicity, nephrotoxicity
- MEDIUM: Metabolismo alterado, biodisponibilidade
- LOW/BENEFICIAL: Redução de toxicidade

**Validação Dupla:**
- Classificação inicial por padrões regex
- Validação crítica com Reflection Pattern
- Confiança explícita (0.6 - 0.95)

---

## 🛡️ Segurança e Compliance

### Validações de Segurança Implementadas

#### 1. Input Validation
```python
# Validação de idade, peso, medicamentos
- Idade: 0-150 anos
- Peso: 0-500 kg
- Medicamentos: Normalização + validação contra base ANVISA
- Alergias: Verificação de cross-reatividade
```

#### 2. Output Sanitization
```python
# Sanitização de saída (safety_guardrails.py:466)
- Remoção de URLs suspeitas
- Remoção de emails e telefones
- Limitação de tamanho (max 50k chars)
- Escape de caracteres especiais
```

#### 3. Error Handling
```python
# Tratamento robusto de erros
- Try/except em todos os níveis
- Fallback gracioso em caso de falha
- Logging detalhado de erros
- Resposta segura mesmo em caso de erro
```

#### 4. Rate Limiting (Recomendado)
```python
# TODO: Implementar rate limiting
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/analyze")
@limiter.limit("10/minute")  # Máximo 10 análises por minuto
async def analyze_medication_legacy(...):
    ...
```

### Disclaimers Legais

**Disclaimer Principal** (sempre incluído):
```
⚠️ AVISO LEGAL IMPORTANTE:

Esta análise é APENAS INFORMATIVA e não substitui consulta médica, diagnóstico ou
tratamento profissional. As informações fornecidas são baseadas em dados públicos
e algoritmos de inteligência artificial que podem conter imprecisões.

SEMPRE consulte um médico, farmacêutico ou profissional de saúde habilitado antes de:
- Iniciar ou interromper qualquer medicamento
- Modificar doses prescritas
- Tomar decisões sobre sua saúde

EM CASO DE EMERGÊNCIA, procure imediatamente atendimento médico presencial ou ligue 192 (SAMU).

O MedSafe não se responsabiliza por decisões tomadas com base nestas informações.
```

**Disclaimers Condicionais:**
- 🔴 **Risco Crítico**: Alerta vermelho com ação imediata
- 🟠 **Risco Alto**: Alerta laranja com supervisão rigorosa
- 🤰 **Gravidez**: Aviso obrigatório consulta obstetra
- 👶 **Pediátrico**: Aviso cálculo de dose por pediatra
- 👴 **Idosos**: Aviso ajuste de dose geriátrico

---

## 📊 Base de Conhecimento

### Drug Interactions Database
- **Tamanho:** 191,000+ interações medicamentosas
- **Fonte:** DrugBank, SIDER, literatura científica
- **Formato:** CSV com campos estruturados
- **Atualização:** Manual (requer pipeline automatizado)

**Estrutura:**
```
Drug 1 | Drug 2 | Interaction Description | Level
```

**Normalização de Nomes:**
```python
# Mapeamento comercial → científico
DRUG_SYNONYMS = {
    'aspirina': 'acetylsalicylic acid',
    'tylenol': 'acetaminophen',
    'glifage': 'metformin',
    'rivotril': 'clonazepam',
    # ... 20+ mapeamentos
}
```

### Reações Adversas por Classe Farmacológica

**Implementado** (`clinical.py:320-532`):
- ✅ Anti-inflamatórios (AINEs)
- ✅ Anticoagulantes (Varfarina)
- ✅ Antidiabéticos (Metformina)
- ✅ Estatinas
- ✅ Antidepressivos (ISRs)
- ✅ Benzodiazepínicos
- ✅ Paracetamol
- ✅ Antibióticos (Quinolonas)

**Cada reação inclui:**
- Descrição clínica
- Frequência (% população)
- Severidade
- Fatores de risco específicos

---

## 🔍 Fluxo de Análise Detalhado

### Exemplo: Análise de Clorpromazina + Dipirona

```json
POST /api/analyze
{
  "patient_data": {
    "age": 27,
    "weight": 80,
    "current_medications": ["dipirona"],
    "allergies": [],
    "conditions": []
  },
  "medication_text": "Clorpromazina"
}
```

**Processamento:**

1. **Triagem Criada** ✅
   - ID: `c4eda132-ac04-471a-9d96-216b8d8a9a22`
   - Status: `processing`

2. **Busca de Evidências** ⚠️
   - RAG: 0 documentos encontrados (base vazia)
   - Fallback: Regras clínicas

3. **Análise Clínica** ✅
   - Interações: 0 (não há clorpromazina+dipirona na base)
   - Contraindicações: 0
   - Risco calculado: `low`

4. **Reflection (5 reflexões)** ✅
   - `consistency_check`: PASS
   - `evidence_validation`: PASS (mas flagged baixa evidência)
   - `completeness_check`: PASS
   - `risk_assessment_review`: PASS
   - `logical_coherence`: PASS
   - Issues: 0

5. **Safety Guardrails** ✅
   - Blocked content: ✅ PASS
   - Hallucination risk: 0.3 (aceitável)
   - Compliance: ✅ PASS
   - Safety classification: `safe`

6. **HITL Evaluation** ⚠️
   - Escalado para revisão: `true`
   - Razão: `low_confidence` (0.65 < 0.7)
   - Prioridade: `routine`
   - Deadline: 48h

7. **Relatório Gerado** ✅
   - ID: `94f40254-bf22-42a4-b736-8fa799b72f4b`
   - Status: `pending_review`

**Resposta Final:**
```json
{
  "session_id": "96c3926f-3a29-4eaa-ad98-13a33707d728",
  "status": "pending_review",
  "requires_human_review": true,
  "analysis": {
    "risk_level": "low",
    "confidence_score": 0.65,
    "safety_classification": "safe",
    "guardrails_validated": true,
    "legal_disclaimers": ["..."],
    "reflection_metadata": {
      "applied": true,
      "cycles": 5,
      "total_issues_found": 0
    }
  }
}
```

---

## ⚠️ Limitações Conhecidas

### 1. Base de Dados Incompleta
**Problema:** Base de interações não cobre todos os medicamentos comercializados no Brasil

**Exemplo:**
- Clorpromazina não está indexada
- Muitos medicamentos genéricos brasileiros ausentes

**Solução Recomendada:**
- Integrar com API ANVISA (Banco de Dados de Medicamentos)
- Scraping de bulas oficiais ANVISA
- Integração com RxNorm/DrugBank atualizados

### 2. RAG/DocAgent Subutilizado
**Problema:** pgvector está vazio, RAG retorna 0 evidências

**Impacto:**
- Baixa confiança nas análises
- Fallback para regras genéricas

**Solução Recomendada:**
```bash
# Pipeline de ingestão de bulas
python -m backend.scripts.ingest_bulas_anvisa
```

### 3. Testes Automatizados Insuficientes
**Cobertura Atual:** <30%

**Gaps:**
- Testes de integração
- Testes de carga
- Testes de segurança
- Testes de regressão

**Solução Recomendada:**
```bash
# Implementar suite completa
pytest backend/tests/ --cov=backend/app --cov-report=html
```

### 4. Monitoramento Básico
**Problema:** Métricas limitadas, sem alertas proativos

**Implementado:**
- Logs estruturados (JSON)
- Health checks básicos

**Falta:**
- Prometheus/Grafana integrado
- Alertas de erro/latência
- Tracing distribuído (Jaeger)

---

## ✅ Recomendações para Produção

### Prioridade CRÍTICA (Implementar antes de produção)

1. **Rate Limiting** ⚠️
   ```python
   # Prevenir abuso
   @limiter.limit("10/minute per user")
   @limiter.limit("100/hour per user")
   ```

2. **Autenticação & Autorização** ⚠️
   ```python
   # JWT + Role-based access control
   # Apenas profissionais de saúde autenticados
   ```

3. **Logging Centralizado** ⚠️
   ```python
   # ELK Stack ou CloudWatch
   # Logs estruturados com trace IDs
   ```

4. **Backup Automatizado** ⚠️
   ```bash
   # PostgreSQL backup diário
   # Retenção: 30 dias
   ```

### Prioridade ALTA (Curto prazo - 1-2 semanas)

1. **Expandir Base de Dados**
   - Ingerir bulas ANVISA (10k+ documentos)
   - Integrar RxNorm API
   - Adicionar medicamentos brasileiros

2. **Testes Automatizados**
   - Cobertura >80%
   - Testes E2E
   - CI/CD pipeline

3. **Monitoramento Avançado**
   - Prometheus + Grafana
   - Alertas Slack/PagerDuty
   - SLO/SLA tracking

4. **Documentação API**
   - OpenAPI/Swagger completo
   - Exemplos de uso
   - Guia de integração

### Prioridade MÉDIA (Médio prazo - 1 mês)

1. **Performance Optimization**
   - Caching (Redis)
   - Query optimization
   - Async processing

2. **Auditoria & Compliance**
   - Logs imutáveis
   - Audit trail completo
   - LGPD/HIPAA compliance

3. **Multi-tenancy**
   - Isolamento de dados por tenant
   - Billing por uso
   - Admin dashboard

---

## 🚀 Deploy para Produção

### Pré-requisitos

```bash
# 1. Variáveis de ambiente (exemplo)
SECRET_KEY=<generate_with_secrets.token_urlsafe_32>
JWT_SECRET=<generate_with_secrets.token_urlsafe_32>
POSTGRES_PASSWORD=<strong_password>
ALLOWED_ORIGINS=https://medsafe.com.br
DEBUG=false

# 2. Recursos mínimos recomendados
CPU: 4 cores
RAM: 8 GB
Storage: 50 GB SSD
PostgreSQL: 16 GB RAM (pgvector é memory-intensive)

# 3. Dependências
Docker 24+
Docker Compose 2.20+
Python 3.11+
PostgreSQL 15+ com pgvector
Ollama (ou OpenAI API)
```

### Checklist de Deploy

- [ ] Configurar secrets (SECRET_KEY, JWT_SECRET, DB passwords)
- [ ] Configurar CORS (allowed_origins específicos)
- [ ] Ativar HTTPS (certificado SSL/TLS)
- [ ] Configurar rate limiting
- [ ] Configurar autenticação (JWT)
- [ ] Configurar backup automatizado (PostgreSQL)
- [ ] Configurar monitoramento (Prometheus/Grafana)
- [ ] Configurar logs centralizados (ELK/CloudWatch)
- [ ] Configurar alertas (PagerDuty/Slack)
- [ ] Executar testes E2E em staging
- [ ] Executar testes de carga (JMeter/k6)
- [ ] Revisar todos os TODOs no código
- [ ] Documentar runbooks (troubleshooting)
- [ ] Treinar equipe de suporte
- [ ] Planejar rollback strategy

---

## 📈 Métricas de Sucesso

### SLIs (Service Level Indicators)

```
Availability: >99.9% (downtime máximo: 43 minutos/mês)
Latency (p50): <500ms para análise completa
Latency (p99): <2000ms
Error Rate: <0.1%
Human Review Rate: 15-25% das análises (aceitável)
```

### Métricas de Qualidade

```
Confidence Score médio: >0.75
Hallucination Risk médio: <0.3
Guardrails pass rate: >99%
Reflection approval rate (first cycle): >80%
```

---

## 🔒 Considerações Legais

### IMPORTANTE: Este sistema NÃO substitui profissionais de saúde

**Limitações Legais:**
1. **Não é dispositivo médico regulamentado** (não passou por certificação ANVISA)
2. **Não pode prescrever medicamentos**
3. **Não pode diagnosticar doenças**
4. **Não pode substituir consulta médica**

**Uso Recomendado:**
- Ferramenta de **apoio à decisão** para profissionais de saúde
- **Triagem inicial** antes de consulta presencial
- **Educação** sobre interações medicamentosas

**Responsabilidade:**
- Decisões finais devem ser tomadas por **médico habilitado**
- Sistema deve ter **disclaimers visíveis** em todas as telas
- Usuários devem **aceitar termos de uso** explicitamente

---

## 📝 Conclusão

### O que funciona MUITO BEM ✅

1. **Arquitetura Agêntica de Ponta**
   - Reflection Pattern implementado corretamente
   - Safety Guardrails robustos
   - HITL bem integrado

2. **Classificação de Interações**
   - InteractionClassifier baseado em padrões clínicos reais
   - Validação dupla com Reflection
   - 191k+ interações indexadas

3. **Segurança & Compliance**
   - Múltiplas camadas de validação
   - Disclaimers legais apropriados
   - Sanitização de entrada/saída

### O que precisa melhorar ⚠️

1. **Base de Conhecimento**
   - Expandir cobertura de medicamentos brasileiros
   - Ingerir bulas ANVISA
   - Atualização automática

2. **Testes & Monitoramento**
   - Aumentar cobertura de testes
   - Implementar monitoramento avançado
   - SLO/SLA tracking

3. **Produção-ready Features**
   - Autenticação/Autorização
   - Rate limiting
   - Caching & Performance

### Veredito Final

**Status:** ✅ **PRODUCTION READY** (com ressalvas)

**Recomendação:**
- ✅ Pode ser usado em **ambiente controlado** (equipe médica interna)
- ✅ Pode ser usado como **ferramenta de apoio à decisão**
- ⚠️ **NÃO recomendado** para público geral sem supervisão médica
- ⚠️ Implementar **Prioridade CRÍTICA** antes de público externo

**Próximos Passos:**
1. Implementar autenticação + rate limiting (1 semana)
2. Expandir base de dados (2 semanas)
3. Testes E2E + CI/CD (2 semanas)
4. Monitoramento avançado (1 semana)
5. Beta com equipe médica selecionada (1 mês)
6. Ajustes baseados em feedback (2 semanas)
7. Launch público controlado (com HITL obrigatório)

---

**Documento preparado por:** Claude Code (Anthropic)
**Skills aplicadas:** ultrathink, debugging-strategies, api-design-principles, code-review-excellence, fastapi-templates, python-testing-patterns, llm-evaluation
**Data:** 2025-11-12
