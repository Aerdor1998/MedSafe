"""
Configuração global para testes pytest
"""

import pytest
import os
import sys

# Adicionar backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def sample_patient_data():
    """Dados de paciente para testes"""
    return {
        "age": 45,
        "gender": "feminino",
        "weight": 60.0,
        "conditions": ["hipertensão", "diabetes tipo 2"],
        "allergies": ["penicilina"],
        "current_medications": ["metformina", "losartana"],
        "supplements": [],
        "alcohol_use": False,
        "smoking": False,
        "pregnancy": False,
        "breastfeeding": False,
        "kidney_function": "normal",
        "liver_function": "normal",
        "additional_info": None
    }

@pytest.fixture
def sample_medication_data():
    """Dados de medicamento para testes"""
    return {
        "medication_text": "Ibuprofeno 400mg",
        "name": "Ibuprofeno",
        "active_ingredient": "ibuprofeno",
        "dosage": "400mg",
        "therapeutic_class": "Anti-inflamatório não esteroidal (AINE)"
    }

@pytest.fixture
def db_connection():
    """Conexão com banco de dados de teste"""
    from models.database import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()
