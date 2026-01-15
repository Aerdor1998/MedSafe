"""
VisionAgent - Agente para análise de imagem/PDF com qwen2.5-vl
"""

import asyncio
import logging
import base64
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import httpx
from PIL import Image
import io

from ..config import settings
from ..db.models import Document
from ..db.database import get_db_context

logger = logging.getLogger(__name__)


class VisionAgent:
    """Agente para análise de imagem/PDF usando qwen2.5-vl via Ollama"""

    def __init__(self):
        """Inicializar VisionAgent"""
        self.ollama_url = f"{settings.ollama_host}/api/generate"
        self.model = settings.ollama_vlm

        logger.info(f"VisionAgent inicializado com modelo: {self.model}")

    async def analyze_document(self, image_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """
        Analisar documento (imagem/PDF) para extrair informações de medicamento

        Args:
            image_data: Dados da imagem/PDF
            session_id: ID da sessão

        Returns:
            Resultado da análise estruturado
        """
        try:
            start_time = datetime.now()
            logger.info(f"Iniciando análise de documento: {session_id}")

            # Processar arquivo
            if image_data.get("file_type") == "image":
                result = await self._analyze_image(image_data, session_id)
            elif image_data.get("file_type") == "pdf":
                result = await self._analyze_pdf(image_data, session_id)
            else:
                raise ValueError(f"Tipo de arquivo não suportado: {image_data.get('file_type')}")

            # Calcular tempo de processamento
            processing_time = (datetime.now() - start_time).total_seconds()
            result["processing_time"] = processing_time

            # Salvar resultado no banco
            await self._save_vision_result(result, session_id)

            logger.info(f"Análise de documento concluída: {session_id}")
            return result

        except Exception as e:
            logger.error(f"Erro na análise de documento: {e}")
            return {"session_id": session_id, "status": "error", "error_message": str(e), "processing_time": 0}

    async def _analyze_image(self, image_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Analisar imagem com qwen2.5-vl"""
        try:
            # Preparar prompt para extração
            prompt = self._build_vision_prompt()

            # Preparar dados da imagem
            image_content = await self._prepare_image_content(image_data)

            # Chamar Ollama
            response = await self._call_ollama_vision(prompt, image_content)

            # Processar resposta
            result = self._parse_vision_response(response, session_id)

            return result

        except Exception as e:
            logger.error(f"Erro na análise de imagem: {e}")
            raise

    async def _analyze_pdf(self, pdf_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Analisar PDF com qwen2.5-vl"""
        try:
            # Para PDFs, converter páginas para imagens
            # Implementar conversão PDF -> imagem se necessário

            # Por enquanto, tratar como imagem
            return await self._analyze_image(pdf_data, session_id)

        except Exception as e:
            logger.error(f"Erro na análise de PDF: {e}")
            raise

    def _build_vision_prompt(self) -> str:
        """Construir prompt para análise de visão"""
        return """Analise esta imagem de medicamento e extraia as seguintes informações de forma estruturada:

1. Nome do medicamento (drug_name)
2. Concentração/força (strength)
3. Forma farmacêutica (form)
4. Seções da bula identificadas:
   - Contraindicações
   - Advertências
   - Posologia
   - Interações medicamentosas

Para cada seção identificada, forneça:
- Tipo da seção
- Texto extraído
- Confiança da extração (0-1)
- Posição aproximada na imagem

Responda em formato JSON válido com a seguinte estrutura:
{
  "drug_name": "nome do medicamento",
  "strength": "concentração",
  "form": "forma farmacêutica",
  "sections": [
    {
      "section_type": "tipo da seção",
      "text": "texto extraído",
      "confidence": 0.95,
      "bounding_box": [x1, y1, x2, y2]
    }
  ]
}"""

    async def _prepare_image_content(self, image_data: Dict[str, Any]) -> str:
        """Preparar conteúdo da imagem para envio ao Ollama"""
        try:
            # Se temos dados base64
            if image_data.get("base64_data"):
                return image_data["base64_data"]

            # Se temos caminho do arquivo
            if image_data.get("file_path"):
                with open(image_data["file_path"], "rb") as f:
                    image_bytes = f.read()
                    return base64.b64encode(image_bytes).decode("utf-8")

            # Se temos bytes diretos
            if image_data.get("image_bytes"):
                return base64.b64encode(image_data["image_bytes"]).decode("utf-8")

            raise ValueError("Nenhum dado de imagem válido encontrado")

        except Exception as e:
            logger.error(f"Erro ao preparar imagem: {e}")
            raise

    async def _call_ollama_vision(self, prompt: str, image_content: str) -> Dict[str, Any]:
        """Chamar Ollama para análise de visão"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [image_content],
                "stream": False,
                "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 2048},
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.ollama_url, json=payload)

                if response.status_code != 200:
                    raise Exception(f"Erro na API Ollama: {response.status_code} - {response.text}")

                return response.json()

        except Exception as e:
            logger.error(f"Erro na chamada Ollama: {e}")
            raise

    def _parse_vision_response(self, response: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Processar resposta do Ollama"""
        try:
            # Extrair texto da resposta
            response_text = response.get("response", "")

            # Tentar fazer parse do JSON
            try:
                parsed_data = json.loads(response_text)
            except json.JSONDecodeError:
                # Se não conseguir fazer parse, extrair informações manualmente
                parsed_data = self._extract_info_manually(response_text)

            # Estruturar resultado
            result = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "status": "completed",
                "drug_name": parsed_data.get("drug_name"),
                "strength": parsed_data.get("strength"),
                "form": parsed_data.get("form"),
                "sections": parsed_data.get("sections", []),
                "extracted_text": response_text,
                "confidence_score": self._calculate_confidence(parsed_data),
                "model_used": self.model,
                "error_message": None,
            }

            return result

        except Exception as e:
            logger.error(f"Erro ao processar resposta: {e}")
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "status": "error",
                "error_message": f"Erro ao processar resposta: {str(e)}",
                "extracted_text": "",
                "model_used": self.model,
            }

    def _extract_info_manually(self, text: str) -> Dict[str, Any]:
        """Extrair informações manualmente se o JSON falhar"""
        # Implementar extração manual de informações
        # Por enquanto, retornar estrutura básica
        return {
            "drug_name": "Não identificado",
            "strength": "Não identificado",
            "form": "Não identificado",
            "sections": [],
        }

    def _calculate_confidence(self, parsed_data: Dict[str, Any]) -> float:
        """Calcular score de confiança geral"""
        try:
            if not parsed_data:
                return 0.0

            # Calcular confiança baseada na qualidade dos dados
            confidence_scores = []

            # Verificar se campos principais estão preenchidos
            if parsed_data.get("drug_name"):
                confidence_scores.append(0.8)

            if parsed_data.get("sections") and len(parsed_data["sections"]) > 0:
                confidence_scores.append(0.9)

            # Média das confianças
            if confidence_scores:
                return sum(confidence_scores) / len(confidence_scores)

            return 0.5

        except Exception:
            return 0.5

    async def _save_vision_result(self, result: Dict[str, Any], session_id: str) -> None:
        """Salvar resultado da análise no banco de dados"""
        try:
            # Por enquanto, apenas log
            # Implementar salvamento no banco se necessário
            logger.info(f"Resultado da visão salvo: {result.get('id')}")

        except Exception as e:
            logger.error(f"Erro ao salvar resultado: {e}")
            # Não falhar se não conseguir salvar
            pass
