"""
Serviço de Visão Computacional usando Qwen2.5VL
Análise de imagens de medicamentos com IA
"""

import base64
import os
import requests
import json
from typing import Optional, Dict, List
from PIL import Image
import io

class VisionService:
    """Serviço para análise de imagens usando modelo Qwen2.5VL"""
    
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        self.vision_model = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """Converter imagem para base64"""
        try:
            # Otimizar imagem antes de enviar
            with Image.open(image_path) as img:
                # Converter para RGB se necessário
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Redimensionar se muito grande
                max_size = 1024
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Converter para bytes
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                image_bytes = buffer.getvalue()
                
                # Codificar em base64
                return base64.b64encode(image_bytes).decode('utf-8')
                
        except Exception as e:
            print(f"Erro ao codificar imagem: {e}")
            return ""
    
    async def analyze_medication_image(self, image_path: str) -> Dict[str, any]:
        """Analisar imagem de medicamento usando IA de visão"""
        try:
            # Codificar imagem
            image_base64 = self._encode_image_to_base64(image_path)
            if not image_base64:
                return {"error": "Erro ao processar imagem"}
            
            # Prompt específico para análise farmacêutica
            prompt = """
Analise esta imagem de medicamento e forneça as seguintes informações em formato JSON:

{
    "medication_name": "nome do medicamento identificado",
    "active_ingredient": "princípio ativo",
    "dosage": "dosagem se visível",
    "manufacturer": "fabricante se visível",
    "batch_info": "lote/validade se visível",
    "medication_type": "comprimido/cápsula/xarope/etc",
    "packaging_type": "caixa/blister/frasco/etc",
    "text_extracted": "todo texto visível na imagem",
    "confidence": 0.85,
    "observations": "observações adicionais sobre a imagem"
}

Instruções específicas:
1. Identifique o nome comercial do medicamento
2. Procure pelo princípio ativo (geralmente em letras menores)
3. Identifique a dosagem (mg, ml, etc.)
4. Note o fabricante/laboratório
5. Se possível, identifique informações de lote e validade
6. Descreva o tipo de medicamento e embalagem
7. Extraia todo texto visível
8. Forneça um nível de confiança (0-1)
9. Adicione observações relevantes

Seja preciso e detalhado. Se algo não estiver visível, indique como "não visível" ou "não identificado".
"""
            
            # Fazer requisição para o modelo de visão
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }]
            
            payload = {
                "model": self.vision_model,
                "messages": messages,
                "temperature": 0.1,  # Baixa temperatura para precisão
                "max_tokens": 1500
            }
            
            response = requests.post(
                f"{self.ollama_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=180  # 3 minutos para análise de imagem
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Tentar extrair JSON da resposta
                return self._parse_vision_response(content)
            else:
                print(f"Erro na API de visão: {response.status_code} - {response.text}")
                return {"error": f"Erro na análise: {response.status_code}"}
                
        except Exception as e:
            print(f"Erro na análise de visão: {e}")
            return {"error": f"Erro interno: {str(e)}"}
    
    def _parse_vision_response(self, content: str) -> Dict[str, any]:
        """Extrair JSON da resposta do modelo de visão"""
        try:
            # Tentar encontrar JSON na resposta
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Validar campos obrigatórios
                required_fields = ["medication_name", "confidence"]
                for field in required_fields:
                    if field not in result:
                        result[field] = "não identificado" if field != "confidence" else 0.0
                
                return result
            else:
                # Se não conseguir extrair JSON, criar estrutura básica
                return {
                    "medication_name": "não identificado",
                    "active_ingredient": "não identificado",
                    "text_extracted": content,
                    "confidence": 0.3,
                    "observations": "Resposta não estruturada do modelo"
                }
                
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON da visão: {e}")
            return {
                "medication_name": "erro na análise",
                "text_extracted": content,
                "confidence": 0.1,
                "error": "Erro ao processar resposta do modelo"
            }
    
    async def extract_text_from_image(self, image_path: str) -> str:
        """Extrair apenas texto da imagem"""
        try:
            image_base64 = self._encode_image_to_base64(image_path)
            if not image_base64:
                return ""
            
            prompt = """
Extraia todo o texto visível desta imagem de medicamento.
Foque em:
- Nome do medicamento
- Princípio ativo
- Dosagem
- Fabricante
- Informações da embalagem
- Qualquer outro texto legível

Retorne apenas o texto extraído, sem comentários adicionais.
"""
            
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }]
            
            payload = {
                "model": self.vision_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 800
            }
            
            response = requests.post(
                f"{self.ollama_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return ""
                
        except Exception as e:
            print(f"Erro na extração de texto: {e}")
            return ""
    
    async def validate_medication_image(self, image_path: str) -> bool:
        """Validar se a imagem contém um medicamento"""
        try:
            image_base64 = self._encode_image_to_base64(image_path)
            if not image_base64:
                return False
            
            prompt = """
Analise se esta imagem contém um medicamento (caixa, comprimidos, cápsulas, frascos, etc.).

Responda apenas com "SIM" ou "NÃO".

SIM se a imagem contém:
- Caixas de medicamentos
- Comprimidos ou cápsulas
- Frascos de remédio
- Bulas ou embalagens farmacêuticas
- Qualquer produto farmacêutico

NÃO se a imagem contém:
- Outros objetos não relacionados a medicamentos
- Texto sem produtos farmacêuticos
- Imagens não relacionadas à área médica
"""
            
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }]
            
            payload = {
                "model": self.vision_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{self.ollama_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip().upper()
                return content.startswith("SIM")
            else:
                return False
                
        except Exception as e:
            print(f"Erro na validação de imagem: {e}")
            return False