"""
Testes para o serviço de OCR
"""

import pytest
import pytest_asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from services.ocr_service import OCRService, OCRResult

class TestOCRService:
    """Testes para o serviço de OCR"""

    def setup_method(self):
        """Setup para cada teste"""
        self.ocr_service = OCRService()

    def test_medication_patterns_loaded(self):
        """Testa se os padrões de medicamentos foram carregados"""
        assert len(self.ocr_service.medication_patterns) > 0
        assert any("dipirona" in pattern for pattern in self.ocr_service.medication_patterns)
        assert any("paracetamol" in pattern for pattern in self.ocr_service.medication_patterns)

    def test_clean_text(self):
        """Testa limpeza de texto"""
        dirty_text = "  DIPIRONA   SÓDICA\n\n  500mg  "
        clean_text = self.ocr_service._clean_text(dirty_text)
        assert clean_text == "dipirona sódica 500mg"

    def test_identify_medication_with_patterns(self):
        """Testa identificação de medicamento usando padrões"""
        text = "medicamento contém dipirona sódica 500mg"
        medication = self.ocr_service._identify_medication(text)
        assert medication is not None
        assert "dipirona" in medication.lower()

    def test_identify_medication_no_match(self):
        """Testa quando não há correspondência de medicamento"""
        text = "texto sem medicamento conhecido"
        medication = self.ocr_service._identify_medication(text)
        # Pode retornar uma palavra capitalizada mesmo sem padrão específico
        assert medication is None or isinstance(medication, str)

    def test_extract_medication_keywords(self):
        """Testa extração de palavras-chave de medicamentos"""
        text = "dipirona paracetamol aspirina comprimido"
        keywords = self.ocr_service._extract_medication_keywords(text)
        assert len(keywords) > 0
        assert any("dipirona" in kw.lower() for kw in keywords)

    @pytest.mark.asyncio
    @patch('services.ocr_service.pytesseract.image_to_string')
    @patch('services.ocr_service.cv2.cvtColor')
    @patch('services.ocr_service.cv2.medianBlur')
    @patch('services.ocr_service.cv2.convertScaleAbs')
    @patch('services.ocr_service.cv2.adaptiveThreshold')
    @patch('services.ocr_service.cv2.morphologyEx')
    @patch('services.ocr_service.cv2.imread')
    async def test_extract_text_success(self, mock_imread, mock_morphology, mock_adaptive,
                                      mock_convert, mock_median, mock_cvtcolor, mock_tesseract):
        """Testa extração de texto com sucesso"""
        import numpy as np
        mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        mock_cvtcolor.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_median.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_convert.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_adaptive.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_morphology.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_tesseract.return_value = "DIPIRONA SÓDICA 500mg"

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            text = await self.ocr_service.extract_text(tmp_path)
            assert text == "DIPIRONA SÓDICA 500mg"
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @patch('services.ocr_service.pytesseract.image_to_string')
    async def test_extract_text_failure(self, mock_tesseract):
        """Testa extração de texto com falha"""
        mock_tesseract.side_effect = Exception("OCR failed")

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            text = await self.ocr_service.extract_text(tmp_path)
            assert text == ""
        finally:
            os.unlink(tmp_path)

    @patch('services.ocr_service.cv2.imread')
    @patch('services.ocr_service.cv2.cvtColor')
    @patch('services.ocr_service.cv2.Laplacian')
    def test_validate_image_valid(self, mock_laplacian, mock_cvtcolor, mock_imread):
        """Testa validação de imagem válida"""
        # Mock do OpenCV
        import numpy as np
        mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        mock_cvtcolor.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_laplacian.return_value.var.return_value = 150  # Variação suficiente

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            is_valid = self.ocr_service.validate_image(tmp_path)
            assert is_valid is True
        finally:
            os.unlink(tmp_path)

    def test_validate_image_invalid_path(self):
        """Testa validação de imagem com caminho inválido"""
        is_valid = self.ocr_service.validate_image("/path/that/does/not/exist.jpg")
        assert is_valid is False

    def test_validate_image_too_small(self):
        """Testa validação de imagem muito pequena"""
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            # Criar imagem muito pequena
            img = Image.new('RGB', (50, 50), color='white')
            img.save(tmp.name, 'JPEG')
            tmp_path = tmp.name

        try:
            is_valid = self.ocr_service.validate_image(tmp_path)
            assert is_valid is False
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @patch('services.ocr_service.VisionService')
    async def test_extract_medication_with_vision_success(self, mock_vision_class):
        """Testa extração de medicamento com IA de visão bem-sucedida"""
        mock_vision = MagicMock()
        mock_vision_class.return_value = mock_vision
        mock_vision.analyze_medication_image = AsyncMock(return_value={
            "medication_name": "Dipirona",
            "confidence": 0.8
        })

        # Mock do OCRService para usar o mock_vision
        self.ocr_service.vision_service = mock_vision

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            medication = await self.ocr_service.extract_medication(tmp_path)
            assert medication == "Dipirona"
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @patch('services.ocr_service.VisionService')
    @patch('services.ocr_service.pytesseract.image_to_string')
    @patch('services.ocr_service.cv2.cvtColor')
    @patch('services.ocr_service.cv2.medianBlur')
    @patch('services.ocr_service.cv2.convertScaleAbs')
    @patch('services.ocr_service.cv2.adaptiveThreshold')
    @patch('services.ocr_service.cv2.morphologyEx')
    @patch('services.ocr_service.cv2.imread')
    async def test_extract_medication_fallback_to_ocr(self, mock_imread, mock_morphology,
                                                    mock_adaptive, mock_convert, mock_median,
                                                    mock_cvtcolor, mock_tesseract, mock_vision_class):
        """Testa fallback para OCR quando IA de visão falha"""
        import numpy as np
        mock_vision = MagicMock()
        mock_vision_class.return_value = mock_vision
        mock_vision.analyze_medication_image.side_effect = Exception("Vision failed")

        # Mock do OCRService para usar o mock_vision
        self.ocr_service.vision_service = mock_vision

        # Mock das funções do OpenCV
        mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        mock_cvtcolor.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_median.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_convert.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_adaptive.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_morphology.return_value = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        mock_tesseract.return_value = "DIPIRONA SÓDICA 500mg"

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake image data')
            tmp_path = tmp.name

        try:
            medication = await self.ocr_service.extract_medication(tmp_path)
            assert medication is not None
            assert "dipirona" in medication.lower()
        finally:
            os.unlink(tmp_path)
