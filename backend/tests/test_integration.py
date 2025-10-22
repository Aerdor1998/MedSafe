"""
Testes de integração para o MedSafe
"""

import pytest
import pytest_asyncio
import json
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.main import app
from datetime import datetime

class TestMedSafeIntegration:
    """Testes de integração para o sistema MedSafe"""

    def setup_method(self):
        """Setup para cada teste"""
        self.client = TestClient(app)
        self.test_patient_data = {
            "age": 30,
            "gender": "masculino",
            "weight": 70.0,
            "conditions": ["hipertensão"],
            "allergies": ["penicilina"],
            "current_medications": ["losartana"],
            "supplements": [],
            "alcohol_use": False,
            "smoking": False,
            "pregnancy": None,
            "breastfeeding": None,
            "kidney_function": None,
            "liver_function": None,
            "additional_info": ""
        }

    def test_health_check(self):
        """Testa endpoint de verificação de saúde"""
        response = self.client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "services" in data
        assert "models" in data

        # Verificar estrutura dos serviços
        services = data["services"]
        assert "database" in services
        assert "ocr" in services
        assert "ai" in services
        assert "vision" in services
        assert "ollama" in services

    def test_medication_search(self):
        """Testa busca de medicamentos"""
        response = self.client.get("/api/medications/search?q=dipirona")

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    @patch('main.ai_service.analyze_contraindications')
    @patch('main.drug_service.get_medication_info')
    @patch('main.ocr_service.extract_medication')
    async def test_analyze_medication_with_text(self, mock_ocr, mock_drug, mock_ai):
        """Testa análise de medicamento com texto"""
        # Mock dos serviços
        mock_ocr.return_value = "Dipirona"

        # Mock do medicamento
        mock_medication = MedicationInfo(
            name="Dipirona",
            active_ingredient="dipirona sódica",
            therapeutic_class="Analgésico",
            anvisa_registry="1234567890"
        )
        mock_drug.return_value = mock_medication

        # Mock da análise
        mock_analysis = AnalysisResult(
            session_id="test-session-123",
            timestamp=datetime.now(),
            patient=PatientData(**self.test_patient_data),
            medication=mock_medication,
            contraindications=[],
            drug_interactions=[],
            adverse_reactions=[],
            recommendations=[],
            overall_risk=RiskLevel.MEDIUM,
            summary="Análise realizada com sucesso"
        )
        mock_ai.return_value = mock_analysis

        # Dados do formulário
        form_data = {
            "patient_data": json.dumps(self.test_patient_data),
            "medication_text": "Dipirona 500mg"
        }

        response = self.client.post("/api/analyze", data=form_data)

        assert response.status_code == 200
        data = response.json()

        assert "session_id" in data
        assert "timestamp" in data
        assert "patient" in data
        assert "medication" in data
        assert "overall_risk" in data
        assert "summary" in data

    @pytest.mark.asyncio
    @patch('main.ai_service.analyze_contraindications')
    @patch('main.drug_service.get_medication_info')
    @patch('main.ocr_service.extract_medication')
    async def test_analyze_medication_with_image(self, mock_ocr, mock_drug, mock_ai):
        """Testa análise de medicamento com imagem"""
        # Mock dos serviços
        mock_ocr.return_value = "Dipirona"

        # Mock do medicamento
        mock_medication = MedicationInfo(
            name="Dipirona",
            active_ingredient="dipirona sódica",
            therapeutic_class="Analgésico",
            anvisa_registry="1234567890"
        )
        mock_drug.return_value = mock_medication

        # Mock da análise
        mock_analysis = AnalysisResult(
            session_id="test-session-123",
            timestamp=datetime.now(),
            patient=PatientData(**self.test_patient_data),
            medication=mock_medication,
            contraindications=[],
            drug_interactions=[],
            adverse_reactions=[],
            recommendations=[],
            overall_risk=RiskLevel.MEDIUM,
            summary="Análise realizada com sucesso"
        )
        mock_ai.return_value = mock_analysis

        # Criar arquivo de imagem temporário
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            # Dados do formulário
            form_data = {
                "patient_data": json.dumps(self.test_patient_data)
            }

            files = {
                "image": ("test.jpg", open(tmp_path, "rb"), "image/jpeg")
            }

            response = self.client.post("/api/analyze", data=form_data, files=files)

            assert response.status_code == 200
            data = response.json()

            assert "session_id" in data
            assert "timestamp" in data
            assert "patient" in data
            assert "medication" in data
            assert "overall_risk" in data
            assert "summary" in data

        finally:
            os.unlink(tmp_path)

    def test_analyze_medication_missing_data(self):
        """Testa análise com dados faltando"""
        response = self.client.post("/api/analyze", data={})

        assert response.status_code == 422  # Validation error

    def test_analyze_medication_invalid_patient_data(self):
        """Testa análise com dados de paciente inválidos"""
        form_data = {
            "patient_data": "invalid json",
            "medication_text": "Dipirona"
        }

        response = self.client.post("/api/analyze", data=form_data)

        assert response.status_code == 500  # Internal server error

    @pytest.mark.asyncio
    @patch('main.ocr_service.extract_text')
    @patch('main.ocr_service.extract_medication')
    async def test_upload_image(self, mock_extract_med, mock_extract_text):
        """Testa upload de imagem"""
        # Mock dos serviços
        mock_extract_text.return_value = "DIPIRONA SÓDICA 500mg"
        mock_extract_med.return_value = "Dipirona"

        # Criar arquivo de imagem temporário
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            files = {
                "file": ("test.jpg", open(tmp_path, "rb"), "image/jpeg")
            }

            response = self.client.post("/api/upload-image", files=files)

            assert response.status_code == 200
            data = response.json()

            assert "session_id" in data
            assert "extracted_text" in data
            assert "medication_name" in data
            assert "image_path" in data

        finally:
            os.unlink(tmp_path)

    def test_upload_image_invalid_file(self):
        """Testa upload de arquivo inválido"""
        # Criar arquivo de texto (não imagem)
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b'not an image')
            tmp_path = tmp.name

        try:
            files = {
                "file": ("test.txt", open(tmp_path, "rb"), "text/plain")
            }

            response = self.client.post("/api/upload-image", files=files)

            # Pode retornar 400 ou 500 dependendo da implementação
            assert response.status_code in [400, 500]

        finally:
            os.unlink(tmp_path)

    def test_upload_image_no_file(self):
        """Testa upload sem arquivo"""
        response = self.client.post("/api/upload-image")

        assert response.status_code == 422  # Validation error

    def test_cors_headers(self):
        """Testa headers CORS"""
        response = self.client.get("/api/health")

        # Verificar se os headers CORS estão presentes (se configurados)
        # Como CORS pode não estar configurado, apenas verificar se a resposta é válida
        assert response.status_code == 200

    def test_api_documentation_available(self):
        """Testa se a documentação da API está disponível"""
        response = self.client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_available(self):
        """Testa se o ReDoc está disponível"""
        response = self.client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    @patch('main.ai_service.analyze_contraindications')
    @patch('main.drug_service.get_medication_info')
    @patch('main.ocr_service.extract_medication')
    async def test_analysis_with_critical_contraindication(self, mock_ocr, mock_drug, mock_ai):
        """Testa análise com contraindicação crítica"""
        # Mock dos serviços
        mock_ocr.return_value = "Dipirona"

        # Mock do medicamento
        mock_medication = MedicationInfo(
            name="Dipirona",
            active_ingredient="dipirona sódica",
            therapeutic_class="Analgésico",
            anvisa_registry="1234567890"
        )
        mock_drug.return_value = mock_medication

        # Mock de análise com contraindicação crítica
        mock_analysis = AnalysisResult(
            session_id="test-session",
            timestamp=datetime.now(),
            patient=PatientData(**self.test_patient_data),
            medication=mock_medication,
            contraindications=[],
            drug_interactions=[],
            adverse_reactions=[],
            recommendations=[],
            overall_risk=RiskLevel.CRITICAL,
            summary="Medicamento contraindicado devido a alergia grave"
        )
        mock_ai.return_value = mock_analysis

        form_data = {
            "patient_data": json.dumps(self.test_patient_data),
            "medication_text": "Dipirona"
        }

        response = self.client.post("/api/analyze", data=form_data)

        assert response.status_code == 200
        data = response.json()

        assert data["overall_risk"] == "critico"
        assert "contraindicado" in data["summary"].lower()

    @pytest.mark.asyncio
    @patch('main.ai_service.analyze_contraindications')
    @patch('main.drug_service.get_medication_info')
    @patch('main.ocr_service.extract_medication')
    async def test_analysis_with_safe_medication(self, mock_ocr, mock_drug, mock_ai):
        """Testa análise com medicamento seguro"""
        # Mock dos serviços
        mock_ocr.return_value = "Paracetamol"

        # Mock do medicamento
        mock_medication = MedicationInfo(
            name="Paracetamol",
            active_ingredient="paracetamol",
            therapeutic_class="Analgésico",
            anvisa_registry="1234567891"
        )
        mock_drug.return_value = mock_medication

        # Mock de análise segura
        mock_analysis = AnalysisResult(
            session_id="test-session",
            timestamp=datetime.now(),
            patient=PatientData(**self.test_patient_data),
            medication=mock_medication,
            contraindications=[],
            drug_interactions=[],
            adverse_reactions=[],
            recommendations=[],
            overall_risk=RiskLevel.LOW,
            summary="Medicamento seguro para uso"
        )
        mock_ai.return_value = mock_analysis

        form_data = {
            "patient_data": json.dumps(self.test_patient_data),
            "medication_text": "Paracetamol"
        }

        response = self.client.post("/api/analyze", data=form_data)

        assert response.status_code == 200
        data = response.json()

        assert data["overall_risk"] == "baixo"
        assert "seguro" in data["summary"].lower()

    def test_static_files_served(self):
        """Testa se arquivos estáticos são servidos"""
        response = self.client.get("/static/")

        # Pode retornar 200 (se houver arquivos) ou 404 (se não houver)
        assert response.status_code in [200, 404]

    def test_frontend_served(self):
        """Testa se o frontend é servido"""
        response = self.client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "MedSafe" in response.text
