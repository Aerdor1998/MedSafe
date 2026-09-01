"""
VisionAgent - LangGraph Multi-Agent System

PATTERN: Vision-Language Model (VLM) for document analysis
SKILLS: @ultrathink, @api-design-principles, @debugging-strategies

RESPONSIBILITIES:
1. Analyze medical document images/PDFs with qwen2.5-vl
2. Extract structured information (drug name, strength, form)
3. Identify bula sections (contraindications, warnings, etc.)
4. Calculate confidence scores for extractions
5. Augment clinical analysis with visual data

INTEGRATION: Works alongside DocumentAgent for hybrid evidence retrieval
"""

import base64
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ..config import settings
from .base_agent import BaseAgent
from .state import MedSafeState

logger = logging.getLogger(__name__)


class VisionAgent(BaseAgent):
    """
    VisionAgent: OCR and visual analysis for medical documents

    MISSION: "See the Evidence" - Extract text and structure from images

    PATTERN: Vision-Language Model (VLM)
    - Uses qwen2.5-vl for multimodal understanding
    - Combines visual and textual analysis
    - Outputs structured medical data

    SKILLS APPLIED:
    - @ultrathink: Clean VLM integration architecture
    - @api-design-principles: RESTful Ollama API interaction
    - @debugging-strategies: Comprehensive error handling
    """

    def __init__(self):
        super().__init__(agent_name="VisionAgent")

        # Vision-specific configuration
        self.vision_model = settings.ollama_vlm  # qwen2.5-vl:7b
        self.ollama_vision_url = f"{settings.ollama_host}/api/generate"

        # Vision model parameters
        self.vision_temperature = 0.1  # Low temp for accurate extraction
        self.vision_max_tokens = 2048

        logger.info(f" VisionAgent initialized with model: {self.vision_model}")

    def get_system_prompt(self) -> str:
        """
        System prompt for VisionAgent

        PATTERN: Specialized vision-focused instructions
        """
        return """You are the VisionAgent for MedSafe, a medical vision specialist.

Your role is to analyze medical document images (bulas, prescriptions, labels) and extract structured information.

EXTRACTION TARGETS:
1. Drug name (generic and brand names)
2. Concentration/strength (e.g., "500mg", "10%")
3. Pharmaceutical form (tablet, capsule, solution, etc.)
4. Bula sections:
   - Contraindications (contraindicações)
   - Warnings (advertências)
   - Dosage (posologia)
   - Drug interactions (interações medicamentosas)
   - Adverse reactions (reações adversas)

OUTPUT FORMAT:
Always respond with valid JSON containing:
{
  "drug_name": "extracted drug name",
  "strength": "concentration with units",
  "form": "pharmaceutical form",
  "sections": [
    {
      "section_type": "contraindications|warnings|dosage|interactions|adverse_reactions",
      "text": "extracted text content",
      "confidence": 0.0-1.0
    }
  ]
}

QUALITY STANDARDS:
- Accuracy > Speed: Take time to read text carefully
- Medical precision: Preserve exact dosages, units, and warnings
- Confidence scoring: Be honest about uncertain extractions
- Portuguese medical terminology: Respect Brazilian standards

If the image is unclear or doesn't contain medical information, set confidence < 0.5 and explain why."""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Process vision analysis request

        PATTERN: Think → Act → Observe (PDF pg 10-13)

        Args:
            state: Current MedSafeState

        Returns:
            Dict with vision analysis results
        """
        try:
            start_time = datetime.now()
            self.log_step(state, "Starting vision analysis")

            # Validate state has image data
            if not self._has_image_data(state):
                self.log_step(state, "No image data found, skipping vision analysis")
                return {}

            # Extract image data from state
            image_info = self._extract_image_data(state)

            # Prepare image for Ollama VLM
            image_base64 = self._prepare_image(image_info)

            # Build vision prompt
            vision_prompt = self._build_vision_prompt(state)

            # Call Ollama VLM
            vision_response = self._call_vision_model(vision_prompt, image_base64)

            # Parse response
            extracted_data = self._parse_vision_response(vision_response)

            # Calculate processing time
            duration = (datetime.now() - start_time).total_seconds()

            self.log_step(
                state,
                f"Vision analysis completed in {duration:.2f}s - "
                f"Drug: {extracted_data.get('drug_name', 'unknown')}, "
                f"Confidence: {extracted_data.get('confidence_score', 0):.2%}",
            )

            # Update state with vision results
            return {
                "vision_analysis": extracted_data,
                "medication_from_image": extracted_data.get("drug_name"),
                "image_confidence": extracted_data.get("confidence_score", 0.0),
                "vision_processing_time": duration,
            }

        except Exception as e:
            logger.error(f"VisionAgent error: {e}", exc_info=True)
            return self.handle_error(state, e, context="Vision analysis failed")

    def _has_image_data(self, state: MedSafeState) -> bool:
        """Check if state contains image data"""
        return "image_data" in state or "image_path" in state or "image_base64" in state

    def _extract_image_data(self, state: MedSafeState) -> Dict[str, Any]:
        """Extract image information from state"""
        image_info = {}

        # Priority: base64 > path > data dict
        if "image_base64" in state:
            image_info["base64_data"] = state["image_base64"]
        elif "image_path" in state:
            image_info["file_path"] = state["image_path"]
        elif "image_data" in state:
            image_info = state["image_data"]

        return image_info

    def _prepare_image(self, image_info: Dict[str, Any]) -> str:
        """
        Prepare image for Ollama VLM

        Args:
            image_info: Dict with image data (base64, path, or bytes)

        Returns:
            Base64 encoded image string
        """
        try:
            # Already base64
            if "base64_data" in image_info:
                return image_info["base64_data"]

            # From file path
            if "file_path" in image_info:
                file_path = Path(image_info["file_path"])
                if not file_path.exists():
                    raise FileNotFoundError(f"Image file not found: {file_path}")

                with open(file_path, "rb") as f:
                    image_bytes = f.read()
                    return base64.b64encode(image_bytes).decode("utf-8")

            # From bytes
            if "image_bytes" in image_info:
                return base64.b64encode(image_info["image_bytes"]).decode("utf-8")

            raise ValueError("No valid image data found in image_info")

        except Exception as e:
            logger.error(f"Error preparing image: {e}")
            raise

    def _build_vision_prompt(self, state: MedSafeState) -> str:
        """
        Build prompt for vision analysis

        PATTERN: Context-aware prompting
        Includes patient context to improve relevance
        """
        base_prompt = """Analyze this medical document image and extract information in JSON format.

Focus on:
1. Drug name (brand and generic)
2. Concentration/strength
3. Pharmaceutical form
4. Key sections from the bula (package insert)

Respond with valid JSON only."""

        # Add patient context if available
        patient_data = state.get("patient_data", {})
        if patient_data:
            age = patient_data.get("age")
            conditions = patient_data.get("conditions", [])

            context = "\n\nPATIENT CONTEXT (for relevance):\n"
            context += f"- Age: {age}\n"
            if conditions:
                context += f"- Conditions: {', '.join(conditions)}\n"

            base_prompt += context

        return base_prompt

    def _call_vision_model(self, prompt: str, image_base64: str) -> Dict[str, Any]:
        """
        Call Ollama VLM API

        PATTERN: Async HTTP with retry logic
        """
        try:
            payload = {
                "model": self.vision_model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": self.vision_temperature,
                    "top_p": 0.9,
                    "num_predict": self.vision_max_tokens,
                },
            }

            # Log API call
            logger.info(
                f"Calling Ollama VLM: {self.vision_model}, "
                f"temp={self.vision_temperature}"
            )

            # Synchronous HTTP call (httpx)
            import httpx

            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.ollama_vision_url, json=payload)

                if response.status_code != 200:
                    raise Exception(
                        f"Ollama VLM API error: {response.status_code} - {response.text}"
                    )

                return response.json()

        except Exception as e:
            logger.error(f"Ollama VLM call failed: {e}")
            raise

    def _parse_vision_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Ollama VLM response

        PATTERN: Defensive JSON parsing with fallback
        """
        try:
            # Extract text from response
            response_text = response.get("response", "")

            # Try to parse as JSON
            try:
                parsed_data = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback: extract JSON from markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                    parsed_data = json.loads(json_str)
                else:
                    # Manual extraction fallback
                    logger.warning(" JSON parsing failed, using manual extraction")
                    parsed_data = self._extract_manually(response_text)

            # Calculate confidence score
            confidence = self._calculate_confidence(parsed_data)

            # Structure result
            result = {
                "id": str(uuid.uuid4()),
                "status": "completed",
                "drug_name": parsed_data.get("drug_name"),
                "strength": parsed_data.get("strength"),
                "form": parsed_data.get("form"),
                "sections": parsed_data.get("sections", []),
                "extracted_text": response_text,
                "confidence_score": confidence,
                "model_used": self.vision_model,
                "timestamp": datetime.now().isoformat(),
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing vision response: {e}", exc_info=True)
            return {
                "id": str(uuid.uuid4()),
                "status": "error",
                "error_message": f"Parse error: {str(e)}",
                "extracted_text": response.get("response", ""),
                "confidence_score": 0.0,
                "model_used": self.vision_model,
            }

    def _extract_manually(self, text: str) -> Dict[str, Any]:
        """
        Manual extraction fallback when JSON parsing fails

        PATTERN: Defensive fallback for robustness
        """
        return {
            "drug_name": "Extraction failed - manual review required",
            "strength": "Unknown",
            "form": "Unknown",
            "sections": [],
            "manual_extraction_needed": True,
        }

    def _calculate_confidence(self, parsed_data: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score

        PATTERN: Multi-factor confidence scoring
        - Drug name present: +0.4
        - Sections found: +0.3
        - Strength/form: +0.15 each
        - Individual section confidences: weighted average
        """
        try:
            if not parsed_data:
                return 0.0

            confidence = 0.0

            # Drug name (most important)
            if parsed_data.get("drug_name") and parsed_data["drug_name"] != "Unknown":
                confidence += 0.4

            # Sections found
            sections = parsed_data.get("sections", [])
            if sections and len(sections) > 0:
                confidence += 0.3

                # Average section confidences
                section_confidences = [s.get("confidence", 0.5) for s in sections]
                if section_confidences:
                    confidence += 0.2 * (
                        sum(section_confidences) / len(section_confidences)
                    )

            # Strength and form
            if parsed_data.get("strength"):
                confidence += 0.05
            if parsed_data.get("form"):
                confidence += 0.05

            return min(confidence, 1.0)  # Cap at 1.0

        except Exception as e:
            logger.warning(f" Confidence calculation error: {e}")
            return 0.5


def create_vision_agent() -> VisionAgent:
    """
    Factory function to create VisionAgent

    PATTERN: Factory pattern for consistent instantiation
    """
    return VisionAgent()
