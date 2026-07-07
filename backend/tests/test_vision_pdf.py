"""
Unit tests for real PDF support in the vision OCR pipeline.

Antes, `VisionAgent._analyze_pdf` tratava os bytes do PDF como se fossem
uma imagem ("Por enquanto, tratar como imagem") — o VLM recebia bytes de
PDF em base64 e a extração falhava sempre. Agora o PDF é rasterizado em
PNGs (pypdfium2, até MAX_PDF_PAGES páginas) enviados ao VLM.
"""

import base64
import io
from unittest.mock import patch

import pypdfium2 as pdfium
import pytest

from backend.app.agents.vision import MAX_PDF_PAGES, VisionAgent


def _make_pdf(num_pages: int) -> bytes:
    doc = pdfium.PdfDocument.new()
    for _ in range(num_pages):
        doc.new_page(200, 200)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestPdfToImages:
    def test_single_page_pdf_renders_one_png(self):
        agent = VisionAgent()
        images = agent._pdf_to_images(_make_pdf(1))

        assert len(images) == 1
        decoded = base64.b64decode(images[0])
        assert decoded.startswith(b"\x89PNG\r\n\x1a\n")

    def test_multi_page_pdf_capped_at_max_pages(self):
        agent = VisionAgent()
        images = agent._pdf_to_images(_make_pdf(MAX_PDF_PAGES + 2))

        assert len(images) == MAX_PDF_PAGES

    def test_invalid_pdf_raises(self):
        agent = VisionAgent()
        with pytest.raises(Exception):
            agent._pdf_to_images(b"isto nao e um pdf")


class TestAnalyzePdfUsesRenderedImages:
    @pytest.mark.asyncio
    async def test_vlm_receives_rendered_pngs_not_raw_pdf(self):
        agent = VisionAgent()
        pdf_bytes = _make_pdf(2)
        captured = {}

        async def _fake_call(prompt, images):
            captured["images"] = images
            return {"response": '{"drug_name": "dipirona", "sections": []}'}

        with patch.object(agent, "_call_ollama_vision", side_effect=_fake_call):
            result = await agent._analyze_pdf(
                {"file_type": "pdf", "image_bytes": pdf_bytes}, "sess-1"
            )

        assert len(captured["images"]) == 2
        for img_b64 in captured["images"]:
            assert base64.b64decode(img_b64).startswith(b"\x89PNG")
        assert result["drug_name"] == "dipirona"
        assert result["status"] == "completed"


class TestAnalyzeImageStillSingle:
    @pytest.mark.asyncio
    async def test_image_path_sends_single_image(self):
        agent = VisionAgent()
        raw = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        captured = {}

        async def _fake_call(prompt, images):
            captured["images"] = images
            return {"response": '{"drug_name": "x", "sections": []}'}

        with patch.object(agent, "_call_ollama_vision", side_effect=_fake_call):
            result = await agent._analyze_image(
                {"file_type": "image", "image_bytes": raw}, "sess-2"
            )

        assert len(captured["images"]) == 1
        assert base64.b64decode(captured["images"][0]) == raw
        assert result["status"] == "completed"
