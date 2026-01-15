# Guia de Migração: API v1 → v2

## 📋 Sumário

A API v2 do MedSafe representa uma refatoração completa da API v1, trazendo melhorias significativas em arquitetura, segurança e funcionalidades.

**Status**:
- ✅ v2 está **PRONTA** e em produção
- ⚠️ v1 está **DEPRECATED** (será removida na versão 3.0)
- 📅 Prazo de migração: **6 meses** a partir de 2025-11-28

---

## 🎯 Por que Migrar?

### v2 Oferece

| Recurso | v1 | v2 |
|---------|----|----|
| **Arquitetura Modular** | ❌ Endpoints inline | ✅ Routers modulares |
| **Rate Limiting** | ❌ Sem proteção | ✅ Configurável por endpoint |
| **Autenticação JWT** | ❌ Sem auth | ✅ JWT completo |
| **Persistência DB** | ⚠️ Parcial | ✅ Completa (Triage + Report) |
| **HITL Workflow** | ❌ Não implementado | ✅ Totalmente integrado |
| **Checkpointing** | ❌ Não | ✅ LangGraph stateful |
| **Optimization Tracking** | ❌ Não | ✅ Performance metrics |
| **Documentação OpenAPI** | ⚠️ Básica | ✅ Completa |
| **Testes Unitários** | ⚠️ Parcial | ✅ Cobertura completa |

---

## 📖 Mapeamento de Endpoints

### 1. Criar Triagem + Análise

**v1** (DEPRECATED):
```http
POST /api/v1/triage
Content-Type: application/json

{
  "age": 65,
  "weight": 70,
  "pregnant": false,
  "cid_codes": ["I10"],
  "meds_in_use": ["Losartan 50mg", "AAS 100mg"],
  "allergies": ["Penicilina"],
  "renal_function": "normal",
  "hepatic_function": "normal",
  "notes": "Hipertenso controlado"
}

Response:
{
  "id": "uuid-triage-id",
  "status": "pending",
  "job_id": "uuid-session-id",
  ...
}
```

**v2** (NOVO):
```http
POST /api/v2/analyze
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "medication": "Losartan 50mg, AAS 100mg",
  "patient_data": {
    "age": 65,
    "weight": 70,
    "pregnant": false,
    "conditions": ["I10"],
    "current_medications": [],
    "allergies": ["Penicilina"],
    "renal_function": "normal",
    "hepatic_function": "normal"
  },
  "user_id": "optional-user-id",
  "notes": "Hipertenso controlado",
  "save_to_db": true
}

Response:
{
  "session_id": "uuid-session-id",
  "triage_id": "uuid-triage-id",
  "status": "pending",
  "message": "Analysis started. Check /api/v2/status/{session_id} for results.",
  "created_at": "2025-11-28T10:30:00Z"
}
```

**Mudanças**:
- ✅ Endpoint: `/api/v1/triage` → `/api/v2/analyze`
- ✅ Agora requer **JWT token** no header `Authorization: Bearer <token>`
- ✅ Campo `medication` consolidado (antes separado)
- ✅ `patient_data` nested object
- ✅ Rate limit: **10 req/min**

---

### 2. Obter Status da Análise

**v1**: Não existia (tinha que polling no banco)

**v2** (NOVO):
```http
GET /api/v2/status/{session_id}
Authorization: Bearer <jwt_token>

Response:
{
  "session_id": "uuid-session-id",
  "triage_id": "uuid-triage-id",
  "status": "completed",  // "pending" | "completed" | "awaiting_human_review"
  "risk_level": "moderate",
  "confidence_score": 0.87,
  "interactions": [...],
  "contraindications": [...],
  "dosage_adjustments": [...],
  "adverse_reactions": [...],
  "evidence_links": [...],
  "requires_human_review": false,
  "escalation_reasons": [],
  "final_report": {...}
}
```

**Benefícios**:
- ✅ Polling eficiente
- ✅ Checkpointing LangGraph (retoma análise de onde parou)
- ✅ Rate limit: **30 req/min**

---

### 3. Obter Relatório de Triagem

**v1** (DEPRECATED):
```http
GET /api/v1/triage/{triage_id}/report

Response:
{
  "triage_id": "uuid",
  "risk_level": "moderate",
  "contraindications": [...],
  "interactions": [...],
  ...
}
```

**v2** (NOVO):
```http
GET /api/v2/triages/{triage_id}/report
Authorization: Bearer <jwt_token>

Response:
{
  "triage_id": "uuid",
  "risk_level": "moderate",
  "contraindications": [...],
  "interactions": [...],
  "dosage_adjustments": [...],
  "adverse_reactions": [...],
  "evidence_links": [...],
  "confidence_score": 0.87,
  "is_final": true,
  "created_at": "2025-11-28T10:35:00Z"
}
```

**Mudanças**:
- ✅ Endpoint: `/api/v1/triage/{id}/report` → `/api/v2/triages/{id}/report`
- ✅ Agora requer **JWT token**
- ✅ Verifica propriedade do recurso (user_id)
- ✅ Campo `is_final` indica se passou por HITL
- ✅ Rate limit: **30 req/min**

---

### 4. Listar Triagens (NOVO em v2)

**v2** (NOVO):
```http
GET /api/v2/triages?page=1&per_page=20&status=completed
Authorization: Bearer <jwt_token>

Response:
{
  "triages": [
    {
      "id": "uuid",
      "status": "completed",
      "age": 65,
      "weight": 70,
      "meds_in_use": ["Losartan 50mg"],
      "created_at": "2025-11-28T10:30:00Z"
    },
    ...
  ],
  "total": 45,
  "page": 1,
  "per_page": 20
}
```

**Benefícios**:
- ✅ Paginação
- ✅ Filtro por status
- ✅ Somente triagens do usuário autenticado

---

### 5. HITL - Human in the Loop (NOVO em v2)

**v2** (NOVO):
```http
POST /api/v2/hitl/approve
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "session_id": "uuid-session-id",
  "approved": true,
  "physician_notes": "Análise revisada e aprovada. Paciente pode iniciar tratamento.",
  "modifications": {
    "risk_level": "low"  // opcional: modificar campos
  }
}

Response:
{
  "session_id": "uuid-session-id",
  "triage_id": "uuid-triage-id",
  "status": "completed",
  "message": "Analysis approved by physician user@example.com",
  ...
}
```

**Benefícios**:
- ✅ Workflow HITL completo
- ✅ Retoma análise de onde parou
- ✅ Salva feedback do médico
- ✅ Rate limit: **20 req/min**

---

## 🔐 Autenticação JWT

### Obter Token (Exemplo)

```http
POST /api/v2/auth/login
Content-Type: application/json

{
  "username": "medico@exemplo.com",
  "password": "senha_segura"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Usar Token

Todos os endpoints v2 requerem header:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## ⚙️ Rate Limiting

| Endpoint | Limite |
|----------|--------|
| `POST /api/v2/analyze` | 10 req/min |
| `GET /api/v2/status/{id}` | 30 req/min |
| `GET /api/v2/triages` | 30 req/min |
| `GET /api/v2/triages/{id}/report` | 30 req/min |
| `POST /api/v2/hitl/approve` | 20 req/min |

**429 Too Many Requests**:
```json
{
  "error": "Rate limit exceeded",
  "detail": "Too many requests. Please try again later.",
  "retry_after": "60"
}
```

---

## 🛠️ Exemplo de Migração (Python)

### v1 (Antigo)
```python
import requests

response = requests.post(
    "http://localhost:9000/api/v1/triage",
    json={
        "age": 65,
        "weight": 70,
        "pregnant": False,
        "cid_codes": ["I10"],
        "meds_in_use": ["Losartan 50mg"],
        "allergies": [],
        "notes": "Paciente hipertenso"
    }
)

triage_id = response.json()["id"]

# Polling manual no banco ou endpoint de report
```

### v2 (Novo)
```python
import requests
import time

# 1. Login para obter token
auth_response = requests.post(
    "http://localhost:9000/api/v2/auth/login",
    json={"username": "medico@exemplo.com", "password": "senha"}
)
token = auth_response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# 2. Iniciar análise
response = requests.post(
    "http://localhost:9000/api/v2/analyze",
    headers=headers,
    json={
        "medication": "Losartan 50mg",
        "patient_data": {
            "age": 65,
            "weight": 70,
            "pregnant": False,
            "conditions": ["I10"],
            "current_medications": [],
            "allergies": []
        },
        "notes": "Paciente hipertenso"
    }
)

session_id = response.json()["session_id"]
triage_id = response.json()["triage_id"]

# 3. Polling de status
while True:
    status_response = requests.get(
        f"http://localhost:9000/api/v2/status/{session_id}",
        headers=headers
    )
    data = status_response.json()

    if data["status"] == "completed":
        print("Análise concluída!")
        print(f"Risco: {data['risk_level']}")
        break
    elif data["status"] == "awaiting_human_review":
        print("Aguardando revisão médica...")
        # Implementar workflow HITL
        break

    time.sleep(5)  # Aguardar 5 segundos antes de checar novamente

# 4. Obter relatório final
report_response = requests.get(
    f"http://localhost:9000/api/v2/triages/{triage_id}/report",
    headers=headers
)
report = report_response.json()
```

---

## 📊 Checklist de Migração

### Para Desenvolvedores

- [ ] Atualizar código para usar `/api/v2/*` endpoints
- [ ] Implementar autenticação JWT
- [ ] Implementar tratamento de rate limiting (429)
- [ ] Adicionar polling de status `/api/v2/status/{session_id}`
- [ ] Implementar workflow HITL (se aplicável)
- [ ] Atualizar testes unitários
- [ ] Atualizar documentação interna

### Para DevOps

- [ ] Configurar Redis para rate limiting (se distribuído)
- [ ] Configurar SECRET_KEY e JWT_SECRET em produção
- [ ] Atualizar health checks para `/api/v2/health`
- [ ] Configurar logs para avisos de deprecation
- [ ] Planejar remoção de v1 (6 meses)

---

## 🚨 Breaking Changes

### Removido em v2

1. **Endpoints inline no main.py** → Movidos para routers modulares
2. **Acesso sem autenticação** → JWT obrigatório
3. **CaptainAgent AG2** → Substituído por LangGraph
4. **Sem rate limiting** → Agora aplicado

### Ainda Funcional (v1)

- `/api/v1/triage` (DEPRECATED, funciona mas será removido)
- `/api/v1/triage/{id}/report` (DEPRECATED, funciona mas será removido)
- `/api/v1/vision/analyze` (PARTIAL DEPRECATION, aguardando VisionAgent LangGraph)

---

## 📞 Suporte

**Documentação Interativa**: [http://localhost:9000/docs](http://localhost:9000/docs)

**Issues**: [GitHub Issues](https://github.com/seu-usuario/medsafe/issues)

**Contato**: medsafe-dev@exemplo.com

---

## 🗓️ Roadmap de Deprecation

| Data | Marco |
|------|-------|
| **2025-11-28** | v2 lançada, v1 marcada como DEPRECATED |
| **2026-02-28** | Avisos de deprecation mais agressivos (3 meses) |
| **2026-05-28** | v1 será removida (6 meses) |

**Prepare-se**: Migre o quanto antes para evitar interrupções.

---

**Última Atualização**: 2025-11-28
