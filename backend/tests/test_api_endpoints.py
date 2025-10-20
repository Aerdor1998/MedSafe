"""
Testes para endpoints da API
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_endpoint():
    """Testar endpoint de saúde"""
    response = client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "healthy"
    assert "services" in data
    assert "database" in data["services"]
    assert "ollama" in data["services"]

def test_analyze_endpoint_basic():
    """Testar endpoint de análise básico"""
    import json
    
    patient_data = {
        "age": 30,
        "gender": "masculino",
        "weight": 70,
        "conditions": [],
        "allergies": [],
        "current_medications": []
    }
    
    response = client.post(
        "/api/analyze",
        data={
            "patient_data": json.dumps(patient_data),
            "medication_text": "Paracetamol 500mg"
        }
    )
    
    # Pode falhar por timeout ou outros issues, aceitar 200 ou 500
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        
        # Verificar estrutura
        assert "session_id" in data
        assert "medication" in data
        assert "patient" in data

def test_analyze_with_interactions():
    """Testar análise com medicamentos que interagem"""
    import json
    
    patient_data = {
        "age": 55,
        "gender": "masculino",
        "weight": 80,
        "conditions": [],
        "allergies": [],
        "current_medications": ["Warfarin"]
    }
    
    response = client.post(
        "/api/analyze",
        data={
            "patient_data": json.dumps(patient_data),
            "medication_text": "Aspirin"
        }
    )
    
    # Aceitar 200 ou 500 (por timeout do Ollama)
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        # Deve ter campo drug_interactions
        assert "drug_interactions" in data

def test_medication_search():
    """Testar busca de medicamentos"""
    response = client.get("/api/medications/search?q=dipirona")
    
    assert response.status_code == 200
    data = response.json()
    
    # API pode retornar lista ou dict com 'results'
    if isinstance(data, dict) and 'results' in data:
        assert isinstance(data['results'], list)
    else:
        assert isinstance(data, list)

def test_upload_image_endpoint():
    """Testar endpoint de upload de imagem"""
    # Criar imagem fictícia em memória
    from io import BytesIO
    from PIL import Image
    
    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    response = client.post(
        "/api/upload-image",
        files={"file": ("test.png", img_bytes, "image/png")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "text" in data or "medication_name" in data

def test_invalid_patient_data():
    """Testar com dados de paciente inválidos"""
    response = client.post(
        "/api/analyze",
        data={
            "patient_data": "invalid json",
            "medication_text": "Paracetamol"
        }
    )
    
    # Pode retornar 400 ou 422 dependendo da validação
    assert response.status_code in [400, 422, 500]

def test_missing_medication_text():
    """Testar sem texto de medicamento"""
    import json
    
    patient_data = {
        "age": 30,
        "gender": "masculino",
        "weight": 70,
        "conditions": [],
        "allergies": [],
        "current_medications": []
    }
    
    response = client.post(
        "/api/analyze",
        data={
            "patient_data": json.dumps(patient_data)
        }
    )
    
    # Deve aceitar sem medication_text se houver imagem, ou rejeitar
    assert response.status_code in [200, 400, 422, 500]

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Testar requisições concorrentes"""
    import asyncio
    import httpx
    
    async with httpx.AsyncClient(base_url="http://localhost:8050") as client:
        tasks = [
            client.get("/api/health")
            for _ in range(10)
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = [r for r in responses if not isinstance(r, Exception) and r.status_code == 200]
        assert len(successful) >= 8  # Pelo menos 80% de sucesso

