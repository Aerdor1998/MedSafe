"""
Configuração global para testes pytest
"""

import pytest

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
def db_session():
    """Sessão de banco de dados para testes"""
    from app.db.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
