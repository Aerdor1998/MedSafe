#!/bin/bash

echo "========================================"
echo "🧪 Teste de Análise REAL de Interações"
echo "========================================"
echo ""

# Teste 1: Paciente sem medicamentos (risco baixo esperado)
echo "📊 Teste 1: Sem medicamentos em uso"
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":45,"weight":70,"pregnant":false,"meds_in_use":[],"conditions":[],"allergies":[]}' \
  -F 'medication_text=Aspirina' | jq -r '.analysis.risk_level, .analysis.interactions | length'

echo ""
sleep 2

# Teste 2: Paciente com Warfarin + Aspirina (interação conhecida)
echo "📊 Teste 2: Warfarin + Aspirina (interação esperada)"
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":60,"weight":75,"pregnant":false,"meds_in_use":[{"name":"Warfarin"}],"conditions":[],"allergies":[]}' \
  -F 'medication_text=Aspirin' | jq -r '.analysis | {risk: .risk_level, interactions: (.interactions | length), model: .model_used}'

echo ""
sleep 2

# Teste 3: Paciente grávida com Methotrexate (contraindicação)
echo "📊 Teste 3: Grávida + Methotrexate (contraindicação)"
curl -s -X POST http://localhost:8000/api/analyze \
  -F 'patient_data={"age":28,"weight":65,"pregnant":true,"meds_in_use":[],"conditions":[],"allergies":[]}' \
  -F 'medication_text=Methotrexate' | jq -r '.analysis | {risk: .risk_level, contraindications: (.contraindications | length)}'

echo ""
echo "========================================"
echo "✅ Testes concluídos!"
echo "========================================"

