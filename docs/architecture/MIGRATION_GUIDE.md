# 🚀 Guia de Migração - Safety Improvements v1.1.0

## ⚡ Quick Start (5 minutos)

### 1. Instalar Dependências (se necessário)

```bash
# Nenhuma dependência nova! Tudo usando libs existentes ✅
```

### 2. Executar Testes

```bash
cd backend

# Testar guardrails
pytest tests/test_safety_guardrails.py -v

# Testar HITL
pytest tests/test_human_in_the_loop.py -v

# Todos os testes
pytest tests/ -v
```

### 3. Iniciar Aplicação

```bash
# Mesmos comandos de sempre
python run.py

# Ou com Docker
docker-compose up
```

**Pronto!** ✅ O sistema já está usando os novos guardrails automaticamente.

---

## 📋 Checklist de Migração

### Para Desenvolvedores

- [ ] Ler SAFETY_IMPROVEMENTS.md completo
- [ ] Executar testes: `pytest backend/tests/test_safety_guardrails.py -v`
- [ ] Executar testes: `pytest backend/tests/test_human_in_the_loop.py -v`
- [ ] Testar endpoint: `GET /api/v1/reviews/pending`
- [ ] Verificar logs para mensagens de guardrails: `🛡️`, `⚠️`, `📋`
- [ ] Ajustar thresholds se necessário (ver seção abaixo)

### Para Médicos/Revisores

- [ ] Acessar dashboard de revisões: `/api/v1/reviews/dashboard/stats`
- [ ] Familiarizar-se com prioridades (EMERGENCY, URGENT, ROUTINE)
- [ ] Testar submissão de revisão (ambiente de dev)
- [ ] Entender estrutura de feedback

### Para DevOps

- [ ] Verificar logs estruturados funcionando
- [ ] Configurar alertas para revisões overdue
- [ ] Monitorar métricas de guardrails
- [ ] Setup notificações para revisões EMERGENCY (TODO: implementar email/Slack)

---

## 🔧 Configuração Personalizada

### Ajustar Critérios de Escalação

```python
# backend/app/config.py (adicionar)

class Settings(BaseSettings):
    # ... existing settings ...

    # Thresholds de escalação (novos)
    hitl_min_confidence: float = 0.7
    hitl_hallucination_threshold: float = 0.5
    hitl_max_contraindications_auto: int = 3
```

```python
# backend/app/agents/human_in_the_loop.py (modificar)

def __init__(self):
    self.escalation_criteria = {
        'min_confidence_threshold': settings.hitl_min_confidence,
        'hallucination_threshold': settings.hitl_hallucination_threshold,
        'max_contraindications_auto': settings.hitl_max_contraindications_auto,
        # ...
    }
```

### Personalizar Disclaimers

```python
# backend/app/agents/safety_guardrails.py

def _load_disclaimers(self):
    return {
        "main": "SEU DISCLAIMER CUSTOMIZADO AQUI...",
        # Adicionar disclaimers específicos da sua instituição
        "custom_institution": """
        AVISO ESPECÍFICO DO HOSPITAL XYZ:
        ...
        """
    }
```

### Adicionar Regras de Negócio Customizadas

```python
# backend/app/agents/safety_guardrails.py

async def validate_analysis(self, analysis, triage_data):
    # Validações padrão...

    # ADICIONAR: Suas validações específicas
    if self._custom_institution_rule_violated(analysis):
        raise GuardrailViolation(
            violation_type="CUSTOM_RULE",
            message="Violação de regra institucional",
            severity="critical"
        )

    return analysis
```

---

## 🔍 Verificação Pós-Migração

### 1. Validar Guardrails Funcionando

```bash
# Executar análise e verificar logs
curl -X POST http://localhost:8000/api/v1/triage \
  -H "Content-Type: application/json" \
  -d '{
    "age": 70,
    "pregnant": false,
    "meds_in_use": ["losartana", "metformina"],
    "cid_codes": ["I10", "E11"]
  }'

# Verificar resposta contém:
# - legal_disclaimers
# - safety_classification
# - guardrails_validated: true
```

### 2. Validar HITL Funcionando

```bash
# Criar caso que requer revisão (risco crítico)
curl -X POST http://localhost:8000/api/v1/triage \
  -H "Content-Type: application/json" \
  -d '{
    "age": 3,
    "meds_in_use": ["varfarina", "aspirina", "ibuprofeno"]
  }'

# Verificar resposta contém:
# - status: "pending_review"
# - requires_human_review: true
# - review_request_id
# - escalation_reasons
```

### 3. Validar Dashboard

```bash
# Obter estatísticas
curl http://localhost:8000/api/v1/reviews/dashboard/stats

# Deve retornar JSON com:
# - total_reviews
# - by_status
# - by_priority
# - overdue_count
# - escalation_reasons_breakdown
```

---

## 🐛 Troubleshooting

### Problema: Testes falhando

**Solução:**
```bash
# Limpar cache pytest
rm -rf .pytest_cache

# Reinstalar dependências
pip install -r requirements.txt

# Rodar testes novamente
pytest backend/tests/ -v
```

### Problema: Guardrails não estão rodando

**Diagnóstico:**
```python
# Verificar se guardrails estão inicializados
from app.agents.safety_guardrails import get_safety_guardrails

guardrails = get_safety_guardrails()
print(guardrails)  # Deve retornar instância
```

**Solução:**
```bash
# Verificar imports no orchestrator
grep -r "safety_guardrails" backend/app/agents/orchestrator.py

# Se não encontrar, o arquivo pode não ter sido atualizado
# Reaplicar edição manualmente
```

### Problema: Endpoint /reviews não encontrado

**Solução:**
```python
# backend/app/main.py - Adicionar router

from app.routers import human_review

app.include_router(human_review.router)
```

### Problema: Todas as análises sendo escaladas

**Causa:** Thresholds muito rigorosos

**Solução:**
```python
# Ajustar thresholds em human_in_the_loop.py
self.escalation_criteria = {
    'min_confidence_threshold': 0.5,  # Menos rigoroso (era 0.7)
    'hallucination_threshold': 0.7,    # Menos sensível (era 0.5)
    'max_contraindications_auto': 5,   # Mais tolerante (era 3)
}
```

### Problema: Disclaimers muito longos

**Solução:**
```python
# Encurtar disclaimers personalizados
# backend/app/agents/safety_guardrails.py

def _load_disclaimers(self):
    return {
        "main": "Versão curta do disclaimer...",
        # Manter apenas essenciais
    }
```

---

## 📊 Métricas de Sucesso

### O que esperar após migração:

| Métrica | Esperado |
|---------|----------|
| % análises com guardrails | **100%** |
| % casos críticos escalados | **> 95%** |
| % falsos positivos | **< 10%** |
| Tempo médio de validação | **< 500ms** |
| Testes passando | **100%** |

### Como medir:

```bash
# 1. Taxa de escalação
curl http://localhost:8000/api/v1/reviews/dashboard/stats | jq '.total_reviews'

# 2. Performance
# Verificar logs: tempo de validação de guardrails

# 3. Qualidade
# Monitorar feedback de revisores: % de análises corretas
```

---

## 🎯 Próximas Etapas

### Após confirmar que tudo funciona:

1. **Setup Notificações**
   - Implementar envio de email para revisores
   - Integrar Slack/Teams para alertas EMERGENCY
   - SMS para casos críticos

2. **Dashboard Web**
   - Frontend para visualização de revisões
   - Interface para submissão de revisões
   - Gráficos de métricas

3. **Integração com Sistema Existente**
   - Conectar com prontuário eletrônico
   - Sincronizar com sistema de agendamento
   - Exportar relatórios para BI

4. **Começar Semana 3-4**
   - Implementar DocAgent com RAG
   - Adicionar Reflection Pattern
   - Ver SAFETY_IMPROVEMENTS.md seção 7

---

## 📚 Recursos Adicionais

### Documentação
- **SAFETY_IMPROVEMENTS.md** - Documentação completa
- **backend/app/agents/safety_guardrails.py** - Código fonte comentado
- **backend/app/agents/human_in_the_loop.py** - Código fonte comentado

### Exemplos de Uso
- **backend/tests/test_safety_guardrails.py** - 30+ exemplos
- **backend/tests/test_human_in_the_loop.py** - 25+ exemplos

### Arquitetura
```
┌─────────────────┐
│  CaptainAgent   │  Orquestrador
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼──────────────┐
│ HITL │  │ SafetyGuardrails│  <- NOVOS!
└──────┘  └─────────────────┘
    │              │
    └──────┬───────┘
           │
    ┌──────▼─────────┐
    │ Clinical Agent │
    └────────────────┘
```

---

## ✅ Conclusão

Após seguir este guia:

- ✅ Sistema de guardrails funcionando
- ✅ Human-in-the-Loop configurado
- ✅ Testes passando
- ✅ Dashboard acessível
- ✅ Documentação atualizada

**Seu sistema MedSafe agora tem:**
- 🛡️ Proteção contra conteúdo perigoso
- 👤 Supervisão humana para casos críticos
- ⚖️ Disclaimers legais obrigatórios
- 🔍 Detecção de alucinações
- ✅ Conformidade regulatória

---

**Versão**: 1.1.0
**Data**: 2025-11-11
**Suporte**: suporte@medsafe.com.br
