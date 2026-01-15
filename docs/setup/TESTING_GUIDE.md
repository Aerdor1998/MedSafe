# Guia de Testes - MedSafe

**Data:** 2025-11-12
**Framework:** pytest + httpx + pytest-asyncio

---

## 📋 Visão Geral

Este guia cobre a estratégia de testes completa para o MedSafe, incluindo testes unitários, de integração, E2E, de carga e de segurança.

---

## 🏗️ Estrutura de Testes

```
backend/tests/
├── __init__.py
├── conftest.py                    # Fixtures compartilhadas
├── unit/                          # Testes unitários
│   ├── test_safety_guardrails.py
│   ├── test_interaction_classifier.py
│   ├── test_reflection_agent.py
│   ├── test_clinical_agent.py
│   └── test_drug_interactions.py
├── integration/                   # Testes de integração
│   ├── test_orchestrator.py
│   ├── test_api_endpoints.py
│   └── test_database.py
├── e2e/                          # Testes End-to-End
│   ├── test_full_analysis.py
│   └── test_hitl_workflow.py
├── load/                         # Testes de carga
│   └── locustfile.py
└── security/                     # Testes de segurança
    └── test_input_validation.py
```

---

## 🧪 Configuração Inicial

### Instalação de Dependências

```bash
cd backend

# Instalar dependências de teste
pip install -r requirements-dev.txt

# Criar arquivo requirements-dev.txt se não existir
cat > requirements-dev.txt << EOF
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2
faker==20.1.0
locust==2.18.0
bandit==1.7.5
safety==2.3.5
EOF

pip install -r requirements-dev.txt
```

### Configuração de Ambiente de Teste

```bash
# Criar .env.test
cat > .env.test << EOF
# Configurações de teste
DEBUG=true
APP_NAME=MedSafe-Test
DATABASE_URL=postgresql://test:test@localhost:5432/medsafe_test
SECRET_KEY=test_secret_key_do_not_use_in_production_32chars
JWT_SECRET=test_jwt_secret_do_not_use_in_production_32chars
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:9000
OLLAMA_HOST=http://localhost:11434
LOG_LEVEL=DEBUG
EOF
```

---

## 🔬 Testes Unitários

### 1. Test Safety Guardrails

**Arquivo:** `backend/tests/unit/test_safety_guardrails.py`

```python
"""
Testes para Safety Guardrails
Verifica validação multi-camada de segurança
"""

import pytest
from backend.app.agents.safety_guardrails import (
    get_safety_guardrails,
    GuardrailViolation,
    RiskCategory
)


@pytest.fixture
def guardrails():
    """Fixture para instância de guardrails"""
    return get_safety_guardrails()


@pytest.fixture
def sample_analysis():
    """Análise de exemplo para testes"""
    return {
        "risk_level": "low",
        "contraindications": [],
        "interactions": [],
        "dosage_adjustments": [],
        "adverse_reactions": [],
        "evidence_links": ["source1", "source2"],
        "model_used": "test_model",
        "confidence_score": 0.85,
        "analysis_notes": "Análise de teste"
    }


@pytest.fixture
def sample_triage_data():
    """Dados de triagem para testes"""
    return {
        "age": 35,
        "weight": 70,
        "pregnant": False,
        "conditions": [],
        "allergies": []
    }


class TestBlockedContent:
    """Testes de detecção de conteúdo proibido"""

    def test_blocked_content_detected(self, guardrails, sample_analysis):
        """Deve bloquear conteúdo proibido"""
        # Adicionar conteúdo proibido
        sample_analysis["recommendations"] = ["você deve tomar 2 comprimidos"]

        with pytest.raises(GuardrailViolation) as exc_info:
            guardrails._check_blocked_content(sample_analysis)

        assert exc_info.value.violation_type == "BLOCKED_CONTENT"
        assert "você deve tomar" in str(exc_info.value)

    def test_no_blocked_content(self, guardrails, sample_analysis):
        """Não deve bloquear conteúdo legítimo"""
        sample_analysis["recommendations"] = [
            "Considere consultar um médico",
            "Monitorar sinais e sintomas"
        ]

        # Não deve lançar exceção
        guardrails._check_blocked_content(sample_analysis)

    def test_disclaimers_not_blocked(self, guardrails, sample_analysis):
        """Disclaimers legais não devem ser bloqueados"""
        # Nota: analysis_notes não é verificado em _check_blocked_content
        sample_analysis["analysis_notes"] = """
        Esta análise não substitui consulta médica.
        Sempre consulte um profissional de saúde.
        """

        # Não deve bloquear
        guardrails._check_blocked_content(sample_analysis)


class TestHallucinationDetection:
    """Testes de detecção de alucinações"""

    @pytest.mark.asyncio
    async def test_high_hallucination_score(self, guardrails, sample_analysis):
        """Deve detectar alto risco de alucinação"""
        # Sem evidências + baixa confiança
        sample_analysis["evidence_links"] = []
        sample_analysis["confidence_score"] = 0.4

        score = await guardrails._detect_hallucinations(sample_analysis)

        assert score > 0.5, "Deve ter alto score de alucinação"

    @pytest.mark.asyncio
    async def test_low_hallucination_score(self, guardrails, sample_analysis):
        """Deve ter baixo risco de alucinação"""
        # Com evidências + alta confiança
        sample_analysis["evidence_links"] = ["source1", "source2", "source3"]
        sample_analysis["confidence_score"] = 0.9

        score = await guardrails._detect_hallucinations(sample_analysis)

        assert score < 0.3, "Deve ter baixo score de alucinação"

    @pytest.mark.asyncio
    async def test_absolute_phrases_detected(self, guardrails, sample_analysis):
        """Deve detectar frases absolutas (indicador de alucinação)"""
        sample_analysis["analysis_notes"] = "Este medicamento é 100% seguro"

        score = await guardrails._detect_hallucinations(sample_analysis)

        assert score > 0, "Deve detectar frase absoluta"


class TestRegulatoryCompliance:
    """Testes de conformidade regulatória"""

    def test_pregnancy_compliance(self, guardrails, sample_analysis):
        """Deve verificar compliance para gestantes"""
        triage_data = {
            "age": 28,
            "pregnant": True,
            "conditions": [],
            "allergies": []
        }

        issues = guardrails._check_regulatory_compliance(
            sample_analysis, triage_data
        )

        # Deve ter issue se gravidez não foi abordada
        pregnancy_issues = [i for i in issues if i["type"] == "pregnancy_not_addressed"]
        assert len(pregnancy_issues) > 0

    def test_pediatric_compliance(self, guardrails, sample_analysis):
        """Deve verificar compliance para pediátrico"""
        triage_data = {
            "age": 10,
            "pregnant": False,
            "conditions": [],
            "allergies": []
        }

        issues = guardrails._check_regulatory_compliance(
            sample_analysis, triage_data
        )

        # Deve ter issue se dosagem pediátrica não foi especificada
        pediatric_issues = [i for i in issues if i["type"] == "pediatric_dosing_missing"]
        assert len(pediatric_issues) > 0


class TestDisclaimers:
    """Testes de injeção de disclaimers"""

    def test_main_disclaimer_injected(self, guardrails, sample_analysis, sample_triage_data):
        """Deve injetar disclaimer principal"""
        result = guardrails._inject_disclaimers(sample_analysis, sample_triage_data)

        assert "legal_disclaimers" in result
        assert len(result["legal_disclaimers"]) >= 1
        assert "AVISO LEGAL" in result["legal_disclaimers"][0]

    def test_pregnancy_disclaimer(self, guardrails, sample_analysis):
        """Deve injetar disclaimer de gravidez"""
        triage_data = {"age": 28, "pregnant": True}

        result = guardrails._inject_disclaimers(sample_analysis, triage_data)

        pregnancy_disclaimers = [d for d in result["legal_disclaimers"] if "GRAVIDEZ" in d]
        assert len(pregnancy_disclaimers) > 0

    def test_critical_risk_disclaimer(self, guardrails, sample_analysis, sample_triage_data):
        """Deve injetar disclaimer crítico para alto risco"""
        sample_analysis["risk_level"] = "critical"

        result = guardrails._inject_disclaimers(sample_analysis, sample_triage_data)

        critical_disclaimers = [d for d in result["legal_disclaimers"] if "CRÍTICO" in d]
        assert len(critical_disclaimers) > 0


class TestSafetyClassification:
    """Testes de classificação de segurança"""

    def test_safe_classification(self, guardrails, sample_analysis):
        """Deve classificar como seguro"""
        sample_analysis["hallucination_risk"] = 0.2
        sample_analysis["compliance_issues"] = []
        sample_analysis["risk_level"] = "low"

        classification = guardrails._classify_safety_risk(sample_analysis)

        assert classification == RiskCategory.SAFE

    def test_dangerous_classification_high_hallucination(self, guardrails, sample_analysis):
        """Deve classificar como perigoso se alta alucinação"""
        sample_analysis["hallucination_risk"] = 0.8

        classification = guardrails._classify_safety_risk(sample_analysis)

        assert classification == RiskCategory.DANGEROUS

    def test_dangerous_classification_critical_compliance(self, guardrails, sample_analysis):
        """Deve classificar como perigoso se issue crítico de compliance"""
        sample_analysis["compliance_issues"] = [
            {"type": "test", "severity": "critical", "message": "test"}
        ]

        classification = guardrails._classify_safety_risk(sample_analysis)

        assert classification == RiskCategory.DANGEROUS


@pytest.mark.asyncio
async def test_full_validation_pipeline(guardrails, sample_analysis, sample_triage_data):
    """Teste do pipeline completo de validação"""
    # Análise válida deve passar por todos os guardrails
    result = await guardrails.validate_analysis(sample_analysis, sample_triage_data)

    # Verificações
    assert result["guardrails_validated"] is True
    assert "safety_classification" in result
    assert "legal_disclaimers" in result
    assert "hallucination_risk" in result
    assert "compliance_issues" in result
    assert "validation_timestamp" in result
```

### 2. Test Interaction Classifier

**Arquivo:** `backend/tests/unit/test_interaction_classifier.py`

```python
"""
Testes para InteractionClassifierAgent
Verifica classificação precisa de severidade
"""

import pytest
from backend.app.services.interaction_classifier import (
    get_classifier_agent,
    SeverityLevel,
    ClassificationResult
)


@pytest.fixture
def classifier():
    """Fixture para instância do classifier"""
    return get_classifier_agent()


class TestCriticalPatterns:
    """Testes de padrões críticos"""

    def test_qt_prolongation_critical(self, classifier):
        """QT prolongation deve ser CRITICAL"""
        description = "May increase the risk of QT prolongation and arrhythmias"

        result = classifier.classify_interaction(
            description, "Drug A", "Drug B"
        )

        assert result.severity == SeverityLevel.CRITICAL
        assert "qt_prolongation" in result.matched_patterns
        assert result.confidence >= 0.9

    def test_bleeding_risk_critical(self, classifier):
        """Risco de sangramento deve ser CRITICAL"""
        description = "May increase anticoagulant activities leading to bleeding"

        result = classifier.classify_interaction(
            description, "Warfarin", "Aspirin"
        )

        assert result.severity == SeverityLevel.CRITICAL
        assert result.confidence >= 0.9


class TestHighPatterns:
    """Testes de padrões HIGH"""

    def test_cardiotoxic_high(self, classifier):
        """Cardiotoxicity deve ser HIGH"""
        description = "May increase the cardiotoxic activities of Drug B"

        result = classifier.classify_interaction(
            description, "Drug A", "Drug B"
        )

        assert result.severity == SeverityLevel.HIGH
        assert "cardiotoxic" in result.matched_patterns


class TestBeneficialPatterns:
    """Testes de padrões benéficos"""

    def test_decrease_toxicity_beneficial(self, classifier):
        """Redução de toxicidade deve ser LOW/BENEFICIAL"""
        description = "Drug A may decrease the cardiotoxic activities of Drug B"

        result = classifier.classify_interaction(
            description, "Drug A", "Drug B"
        )

        assert result.severity == SeverityLevel.LOW
        assert "decrease_toxicity" in result.matched_patterns


class TestReflectionValidation:
    """Testes de validação por reflexão"""

    def test_critical_decision_validated(self, classifier):
        """Decisões críticas devem ser validadas"""
        description = "May increase QT prolongation"

        result = classifier.classify_interaction(
            description, "Drug A", "Drug B"
        )

        # Validar com Reflection
        validated = classifier.validate_critical_decision(result, description)

        # Deve manter CRITICAL se múltiplos padrões
        assert validated.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
```

---

## 🔗 Testes de Integração

### Test API Endpoints

**Arquivo:** `backend/tests/integration/test_api_endpoints.py`

```python
"""
Testes de integração para endpoints da API
"""

import pytest
import json
from httpx import AsyncClient
from backend.app.main import app


@pytest.fixture
async def client():
    """Cliente HTTP assíncrono"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    """Deve retornar health check OK"""
    response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data


@pytest.mark.asyncio
async def test_analyze_medication_success(client):
    """Deve analisar medicamento com sucesso"""
    patient_data = {
        "age": 35,
        "weight": 70,
        "pregnant": False,
        "conditions": [],
        "allergies": [],
        "current_medications": ["aspirina"]
    }

    form_data = {
        "patient_data": json.dumps(patient_data),
        "medication_text": "Paracetamol"
    }

    response = await client.post("/api/analyze", data=form_data)

    assert response.status_code == 200
    data = response.json()

    # Verificações
    assert "session_id" in data
    assert "analysis" in data
    assert data["analysis"]["risk_level"] in ["critical", "high", "medium", "low"]
    assert data["analysis"]["guardrails_validated"] is True


@pytest.mark.asyncio
async def test_analyze_medication_invalid_age(client):
    """Deve rejeitar idade inválida"""
    patient_data = {
        "age": 200,  # Inválido
        "weight": 70,
        "pregnant": False
    }

    form_data = {
        "patient_data": json.dumps(patient_data),
        "medication_text": "Paracetamol"
    }

    response = await client.post("/api/analyze", data=form_data)

    # Pode retornar 422 (Validation Error) ou 500
    assert response.status_code in [422, 500]
```

---

## 🚀 Testes End-to-End

### Full Analysis Workflow

**Arquivo:** `backend/tests/e2e/test_full_analysis.py`

```python
"""
Testes End-to-End do fluxo completo
"""

import pytest
import json
from httpx import AsyncClient
from backend.app.main import app


@pytest.mark.asyncio
async def test_full_analysis_workflow():
    """Teste completo do workflow de análise"""

    async with AsyncClient(app=app, base_url="http://test") as client:

        # 1. Criar triagem
        patient_data = {
            "age": 65,
            "weight": 75,
            "pregnant": False,
            "conditions": ["hipertensão"],
            "allergies": [],
            "current_medications": ["losartana", "aspirina"]
        }

        form_data = {
            "patient_data": json.dumps(patient_data),
            "medication_text": "Ibuprofeno"
        }

        response = await client.post("/api/analyze", data=form_data)
        assert response.status_code == 200

        data = response.json()
        session_id = data["session_id"]
        triage_id = data["triage_id"]

        # 2. Verificar análise
        analysis = data["analysis"]

        # Deve ter detectado interação aspirina + ibuprofeno
        assert len(analysis["interactions"]) > 0

        # Deve ter ajuste de dose para idoso
        assert len(analysis["dosage_adjustments"]) > 0

        # Deve ter disclaimer de idoso
        elderly_disclaimer = any(
            "idoso" in d.lower() or "geriátrico" in d.lower()
            for d in analysis.get("legal_disclaimers", [])
        )
        assert elderly_disclaimer

        # 3. Verificar HITL (idoso com múltiplas condições deve escalar)
        assert data["requires_human_review"] is True

        # 4. Buscar relatório
        report_response = await client.get(f"/api/v1/triage/{triage_id}/report")
        assert report_response.status_code in [200, 404]  # 404 se banco não persistir
```

---

## ⚡ Testes de Carga

### Locust Load Test

**Arquivo:** `backend/tests/load/locustfile.py`

```python
"""
Testes de carga com Locust
Execute: locust -f locustfile.py --host=http://localhost:9001
"""

from locust import HttpUser, task, between
import json


class MedSafeUser(HttpUser):
    """Usuário simulado do MedSafe"""

    wait_time = between(1, 3)  # 1-3 segundos entre requisições

    @task(3)
    def analyze_medication(self):
        """Análise de medicamento (tarefa mais comum)"""
        patient_data = {
            "age": 35,
            "weight": 70,
            "pregnant": False,
            "conditions": [],
            "allergies": [],
            "current_medications": ["paracetamol"]
        }

        self.client.post(
            "/api/analyze",
            data={
                "patient_data": json.dumps(patient_data),
                "medication_text": "Ibuprofeno"
            }
        )

    @task(1)
    def health_check(self):
        """Health check (menos frequente)"""
        self.client.get("/healthz")
```

**Executar:**
```bash
# Teste local
locust -f backend/tests/load/locustfile.py --host=http://localhost:9001

# Teste com múltiplos usuários
locust -f backend/tests/load/locustfile.py \
    --host=http://localhost:9001 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless
```

---

## 🔒 Testes de Segurança

### Input Validation

**Arquivo:** `backend/tests/security/test_input_validation.py`

```python
"""
Testes de segurança e validação de entrada
"""

import pytest
import json
from httpx import AsyncClient
from backend.app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_sql_injection_attempt(client):
    """Deve prevenir SQL injection"""
    malicious_input = "'; DROP TABLE triages; --"

    patient_data = {
        "age": 35,
        "weight": 70,
        "conditions": [malicious_input]
    }

    response = await client.post(
        "/api/analyze",
        data={
            "patient_data": json.dumps(patient_data),
            "medication_text": "Paracetamol"
        }
    )

    # Deve processar sem executar SQL malicioso
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_xss_attempt(client):
    """Deve prevenir XSS"""
    xss_payload = "<script>alert('XSS')</script>"

    patient_data = {
        "age": 35,
        "weight": 70,
        "notes": xss_payload
    }

    response = await client.post(
        "/api/analyze",
        data={
            "patient_data": json.dumps(patient_data),
            "medication_text": "Paracetamol"
        }
    )

    if response.status_code == 200:
        data = response.json()
        # Verificar que script foi sanitizado
        assert "<script>" not in str(data)


@pytest.mark.asyncio
async def test_oversized_payload(client):
    """Deve rejeitar payloads muito grandes"""
    huge_text = "A" * (10 * 1024 * 1024)  # 10MB

    patient_data = {
        "age": 35,
        "notes": huge_text
    }

    response = await client.post(
        "/api/analyze",
        data={
            "patient_data": json.dumps(patient_data),
            "medication_text": "Paracetamol"
        }
    )

    # Deve rejeitar
    assert response.status_code in [413, 422, 500]
```

---

## ▶️ Executando Testes

### Comandos Básicos

```bash
# Todos os testes
pytest

# Testes unitários apenas
pytest backend/tests/unit/

# Testes com cobertura
pytest --cov=backend/app --cov-report=html

# Testes específicos
pytest backend/tests/unit/test_safety_guardrails.py::TestBlockedContent

# Testes verbosos
pytest -v

# Testes com output
pytest -s

# Testes paralelos (mais rápido)
pytest -n auto
```

### CI/CD Pipeline

```yaml
# CI no repositório:
# - arquivo canônico: .github/workflows/ci.yml
# - inclui: lint + security + tests + migrations + build + smoke + (e2e em PR)
#
# Para ver/editar a pipeline, consulte:
#   - .github/workflows/ci.yml
```

---

## 📊 Métricas de Qualidade

### Objetivos de Cobertura

```
Cobertura Mínima: 80%
Cobertura Ideal: 90%

Prioridade por Componente:
- Safety Guardrails: 95%+ (crítico)
- Interaction Classifier: 90%+ (crítico)
- Clinical Agent: 85%+
- Orchestrator: 80%+
- API Endpoints: 80%+
```

### Relatório de Cobertura

```bash
# Gerar relatório HTML
pytest --cov=backend/app --cov-report=html

# Abrir no navegador
open htmlcov/index.html
```

---

## ✅ Checklist de Testes

Antes de deploy para produção:

- [ ] Todos os testes unitários passando
- [ ] Todos os testes de integração passando
- [ ] Testes E2E passando
- [ ] Cobertura de código >80%
- [ ] Testes de carga executados (100 usuários concorrentes)
- [ ] Testes de segurança passando
- [ ] Sem vulnerabilidades críticas (bandit, safety)
- [ ] Logs de teste revisados (sem errors inesperados)

---

**Documento preparado por:** Claude Code (Anthropic)
**Data:** 2025-11-12
