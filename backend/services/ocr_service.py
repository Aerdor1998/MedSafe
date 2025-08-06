"""
Serviço de OCR para reconhecimento de medicamentos em imagens
"""

import cv2
import numpy as np
import pytesseract
import re
from PIL import Image
from typing import Optional, Dict, List
import os
from dataclasses import dataclass
from .vision_service import VisionService

@dataclass
class OCRResult:
    text: str
    confidence: float
    medication_name: Optional[str] = None

class OCRService:
    """Serviço para extrair texto e identificar medicamentos em imagens"""
    
    def __init__(self):
        self.tesseract_config = r'--oem 3 --psm 6 -l por+eng'
        self.medication_patterns = self._load_medication_patterns()
        self.vision_service = VisionService()
        self.use_ai_vision = True  # Priorizar IA de visão sobre OCR tradicional
    
    def _load_medication_patterns(self) -> List[str]:
        """Carregar padrões de nomes de medicamentos comuns"""
        return [
            # Analgésicos/Antipiréticos
            r'dipirona|novalgina|metamizol',
            r'paracetamol|acetaminofeno|tylenol',
            r'aspirina|ácido acetilsalicílico|aas',
            
            # Anti-inflamatórios
            r'ibuprofeno|advil|alivium',
            r'diclofenaco|voltaren|cataflan',
            r'nimesulida|nisulid|scaflan',
            
            # Antibióticos
            r'amoxicilina|amoxil|novamox',
            r'azitromicina|azalid|zitromax',
            r'cefalexina|keflex|ceporex',
            
            # Outros comuns
            r'omeprazol|losec|peprazol',
            r'sinvastatina|zocor|sinvacor',
            r'enalapril|renitec|vasotec',
            r'metformina|glifage|diabinese'
        ]
    
    async def extract_text(self, image_path: str) -> str:
        """Extrair todo o texto da imagem"""
        try:
            # Pré-processamento da imagem
            processed_image = self._preprocess_image(image_path)
            
            # OCR com Tesseract
            text = pytesseract.image_to_string(
                processed_image, 
                config=self.tesseract_config
            )
            
            return text.strip()
            
        except Exception as e:
            print(f"Erro no OCR: {e}")
            return ""
    
    async def extract_medication(self, image_path: str) -> Optional[str]:
        """Extrair e identificar nome do medicamento usando IA de visão + OCR"""
        try:
            medication_name = None
            
            # Primeiro: tentar com IA de visão (mais preciso)
            if self.use_ai_vision:
                try:
                    vision_result = await self.vision_service.analyze_medication_image(image_path)
                    if vision_result.get("confidence", 0) > 0.5:
                        medication_name = vision_result.get("medication_name")
                        if medication_name and medication_name != "não identificado":
                            print(f"✅ Medicamento identificado por IA: {medication_name}")
                            return medication_name
                except Exception as e:
                    print(f"⚠️ Erro na IA de visão, usando OCR tradicional: {e}")
            
            # Fallback: OCR tradicional
            full_text = await self.extract_text(image_path)
            if not full_text:
                return None
            
            # Limpar e normalizar texto
            clean_text = self._clean_text(full_text)
            
            # Procurar por padrões de medicamentos
            medication_name = self._identify_medication(clean_text)
            
            if medication_name:
                print(f"✅ Medicamento identificado por OCR: {medication_name}")
            
            return medication_name
            
        except Exception as e:
            print(f"Erro na identificação do medicamento: {e}")
            return None
    
    def _preprocess_image(self, image_path: str) -> np.ndarray:
        """Pré-processar imagem para melhorar OCR"""
        # Carregar imagem
        image = cv2.imread(image_path)
        
        if image is None:
            raise ValueError(f"Não foi possível carregar a imagem: {image_path}")
        
        # Converter para escala de cinza
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Aplicar filtro para reduzir ruído
        denoised = cv2.medianBlur(gray, 3)
        
        # Aumentar contraste
        contrast = cv2.convertScaleAbs(denoised, alpha=1.5, beta=10)
        
        # Binarização adaptativa
        binary = cv2.adaptiveThreshold(
            contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Morfologia para limpar texto
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _clean_text(self, text: str) -> str:
        """Limpar e normalizar texto extraído"""
        # Converter para minúsculas
        text = text.lower()
        
        # Remover caracteres especiais mantendo letras, números e espaços
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remover espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Remover quebras de linha
        text = text.replace('\n', ' ')
        
        return text.strip()
    
    def _identify_medication(self, text: str) -> Optional[str]:
        """Identificar medicamento no texto usando padrões"""
        # Tentar identificar por padrões regex
        for pattern in self.medication_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0].title()
        
        # Tentar identificar por palavras-chave comuns
        medication_keywords = self._extract_medication_keywords(text)
        if medication_keywords:
            return medication_keywords[0]
        
        # Buscar por padrões de nomes comerciais (palavras capitalizadas)
        commercial_names = re.findall(r'\b[A-Z][a-z]+\b', text)
        for name in commercial_names:
            if len(name) > 3:  # Filtrar palavras muito curtas
                return name
        
        return None
    
    def _extract_medication_keywords(self, text: str) -> List[str]:
        """Extrair palavras que podem ser nomes de medicamentos"""
        words = text.split()
        medication_words = []
        
        # Filtrar palavras que podem ser medicamentos
        for word in words:
            # Palavras com pelo menos 4 caracteres
            if len(word) >= 4:
                # Que não sejam palavras comuns
                if word not in ['comprimido', 'cápsula', 'medicamento', 'farmácia', 'dose']:
                    # E que tenham características de nomes de medicamentos
                    if re.match(r'^[a-zA-Z]+$', word):
                        medication_words.append(word.title())
        
        return medication_words
    
    async def get_ocr_result_with_confidence(self, image_path: str) -> OCRResult:
        """Obter resultado completo usando IA de visão + OCR com nível de confiança"""
        try:
            text = ""
            confidence = 0.0
            medication_name = None
            
            # Tentar com IA de visão primeiro
            if self.use_ai_vision:
                try:
                    vision_result = await self.vision_service.analyze_medication_image(image_path)
                    if vision_result.get("confidence", 0) > 0.3:
                        text = vision_result.get("text_extracted", "")
                        confidence = vision_result.get("confidence", 0.0)
                        medication_name = vision_result.get("medication_name")
                        
                        if medication_name and medication_name != "não identificado":
                            return OCRResult(
                                text=text,
                                confidence=confidence,
                                medication_name=medication_name
                            )
                except Exception as e:
                    print(f"Erro na IA de visão: {e}")
            
            # Fallback para OCR tradicional
            text = await self.extract_text(image_path)
            
            if text:
                # Obter dados detalhados do Tesseract
                processed_image = self._preprocess_image(image_path)
                data = pytesseract.image_to_data(
                    processed_image, 
                    config=self.tesseract_config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Calcular confiança média
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            
            # Identificar medicamento
            if not medication_name:
                medication_name = await self.extract_medication(image_path)
            
            return OCRResult(
                text=text,
                confidence=confidence,
                medication_name=medication_name
            )
            
        except Exception as e:
            print(f"Erro no OCR detalhado: {e}")
            return OCRResult(text="", confidence=0.0)
    
    def validate_image(self, image_path: str) -> bool:
        """Validar se a imagem é adequada para OCR"""
        try:
            # Verificar se arquivo existe
            if not os.path.exists(image_path):
                return False
            
            # Verificar se é uma imagem válida
            image = cv2.imread(image_path)
            if image is None:
                return False
            
            # Verificar dimensões mínimas
            height, width = image.shape[:2]
            if height < 100 or width < 100:
                return False
            
            # Verificar se não está muito borrada (usando Laplacian)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Threshold para imagens muito borradas
            if laplacian_var < 100:
                return False
            
            return True
            
        except Exception:
            return False