# 🧪 Guia de Testes - Análise REAL de Interações Medicamentosas

## ✅ Sistema Implementado

O MedSafe agora realiza análise **REAL** de interações medicamentosas usando:
- **Base de dados:** 191.542 interações medicamentosas
- **Sinônimos:** 20+ medicamentos mapeados (nomes comerciais ↔ científicos)
- **Classificação automática:** Severidade (critical, high, medium, low)
- **Categorias:** Cardiovascular, Hepática, Renal, Neurológica, Coagulação, etc.

---

## 🧪 Testes Recomendados

### Teste 1: Varfarina + Aspirina (Interação Alta - Coagulação)

**Cenário:** Paciente idoso usando Varfarina, prescrevendo Aspirina

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":65,"weight":80,"pregnant":false,"meds_in_use":[{"name":"Varfarina"}],"conditions":[],"allergies":[]}' \
  -F 'medication_text=Aspirina' | jq '.analysis.interactions[0]'
```

**Resultado Esperado:**
- ✅ Risco: MEDIUM ou HIGH
- ✅ Interação encontrada
- ✅ Categoria: Coagulação
- ✅ Recomendação: Usar com extrema cautela

---

### Teste 2: Metformina + Levofloxacin (Interação - Hipoglicemia)

**Cenário:** Diabético usando Metformina, prescrevendo antibiótico

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":55,"weight":75,"pregnant":false,"meds_in_use":[{"name":"Metformina"}],"conditions":["diabetes"],"allergies":[]}' \
  -F 'medication_text=Levofloxacin' | jq '{
  risco: .analysis.risk_level,
  interacoes: .analysis.interactions
}'
```

**Resultado Esperado:**
- ✅ Interação: "Metformin may increase the hypoglycemic activities of Levofloxacin"
- ✅ Severidade: high
- ✅ Categoria: Farmacológica

---

### Teste 3: Paciente Grávida + Methotrexate (Contraindicação Crítica)

**Cenário:** Gestante, prescrevendo Methotrexate

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":28,"weight":65,"pregnant":true,"meds_in_use":[],"conditions":[],"allergies":[]}' \
  -F 'medication_text=Methotrexate' | jq '{
  risco: .analysis.risk_level,
  contraindicacoes: .analysis.contraindications
}'
```

**Resultado Esperado:**
- ✅ Risco: CRITICAL ou HIGH
- ✅ Contraindicação por gravidez
- ✅ Recomendação: Não usar

---

### Teste 4: Paciente Idoso (Ajuste de Dosagem)

**Cenário:** Paciente >65 anos

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":75,"weight":65,"pregnant":false,"meds_in_use":[],"conditions":[],"allergies":[]}' \
  -F 'medication_text=Diazepam' | jq '.analysis.dosage_adjustments'
```

**Resultado Esperado:**
- ✅ Ajuste: "Paciente idoso (≥65 anos)"
- ✅ Recomendação: Dose reduzida

---

### Teste 5: Múltiplos Medicamentos em Uso

**Cenário:** Polimedicação (3+ medicamentos)

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":60,"weight":80,"pregnant":false,"meds_in_use":[{"name":"Varfarina"},{"name":"Metformina"},{"name":"Omeprazol"}],"conditions":["diabetes","hipertensão"],"allergies":[]}' \
  -F 'medication_text=Aspirina' | jq '{
  risco: .analysis.risk_level,
  total_interacoes: (.analysis.interactions | length)
}'
```

**Resultado Esperado:**
- ✅ Múltiplas interações detectadas
- ✅ Risco elevado conforme número de interações

---

## 📊 Medicamentos Suportados (Sinônimos)

### Anti-inflamatórios
- **Aspirina** → Acetylsalicylic acid
- **Ibuprofeno** → Ibuprofen
- **Dipirona** → Metamizole

### Anticoagulantes
- **Varfarina** → Warfarin
- **Marevan** → Warfarin

### Antidiabéticos
- **Metformina** → Metformin
- **Glifage** → Metformin

### Antidepressivos
- **Fluoxetina** → Fluoxetine
- **Prozac** → Fluoxetine
- **Sertralina** → Sertraline
- **Zoloft** → Sertraline

### Estatinas
- **Atorvastatina** → Atorvastatin
- **Simvastatina** → Simvastatin

### Anti-hipertensivos
- **Losartana** → Losartan

### Outros
- **Omeprazol** → Omeprazole
- **Paracetamol** → Acetaminophen
- **Amoxicilina** → Amoxicillin
- **Diazepam** → Diazepam (Valium)
- **Clonazepam** → Clonazepam (Rivotril)

---

## 🎯 Como Adicionar Novo Medicamento

Edite `/backend/app/services/drug_interactions.py`:

```python
DRUG_SYNONYMS = {
    # ...
    'novo_nome_comercial': 'nome_cientifico',
    'marca_popular': 'nome_cientifico',
}
```

---

## 📈 Níveis de Risco

| Nível | Descrição | Ação |
|-------|-----------|------|
| **🟢 LOW** | Risco baixo | Acompanhamento de rotina |
| **🟡 MEDIUM** | Risco moderado | Usar com cautela e monitoramento |
| **🟠 HIGH** | Risco alto | Supervisão médica rigorosa |
| **🔴 CRITICAL** | Risco crítico | CONTRAINDICADO |

---

## 🔍 Categorias de Interação

- **Cardiovascular:** Arritmias, pressão arterial
- **Coagulação:** Sangramento, trombose
- **Hepática:** Toxicidade hepática
- **Renal:** Função renal comprometida
- **Neurológica:** SNC, sedação
- **Farmacocinética:** Metabolismo (CYP450)
- **Fotossensibilidade:** Reações à luz solar

---

## ✅ Verificar se Está Funcionando

```bash
# 1. Backend rodando
curl http://localhost:8000/healthz

# 2. Base de interações carregada
tail -f /tmp/medsafe.log | grep "Base carregada"
# Deve mostrar: "✅ Base carregada: 382270 interações indexadas"

# 3. Teste rápido
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":65,"meds_in_use":[{"name":"Varfarina"}]}' \
  -F 'medication_text=Aspirina' | jq '.analysis.interactions | length'
# Deve retornar: 1 (ou mais)
```

---

## 🐛 Troubleshooting

### Interação não encontrada

**Possíveis causas:**
1. Nome do medicamento não mapeado em `DRUG_SYNONYMS`
2. Medicamento não existe na base CSV
3. Grafia incorreta

**Solução:**
- Adicionar sinônimo no dicionário
- Verificar se medicamento está no CSV: `grep -i "MEDICAMENTO" data/db_drug_interactions.csv`

### Sempre retorna "risco baixo"

**Causa:** Versão antiga do código ainda em memória

**Solução:**
```bash
pkill -f uvicorn
./start.sh
```

---

## 📞 Suporte

Para adicionar novos medicamentos ou reportar problemas:
1. Verificar logs: `tail -f /tmp/medsafe.log`
2. Verificar base de dados: `data/db_drug_interactions.csv`
3. Adicionar sinônimos em: `backend/app/services/drug_interactions.py`

---

**Última atualização:** 08/10/2025
**Versão:** 1.0.0 - Análise REAL implementada ✅

