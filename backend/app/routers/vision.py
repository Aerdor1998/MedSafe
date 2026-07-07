"""
Vision (OCR/VLM) API - v2

Provides a stable v2 endpoint for image/PDF analysis so the frontend does not rely on legacy v1 routes.
"""

import logging
import uuid
from io import BytesIO
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from PIL import Image

from ..agents.vision import VisionAgent
from ..auth.jwt import get_optional_current_user
from ..config import settings as app_settings
from ..middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/vision", tags=["vision"])


@router.post("/analyze")
@limiter.limit("15/minute")
async def analyze_vision(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[str] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """
    Analyze an uploaded image/PDF and extract medication information.

    Anonymous access is allowed only when explicitly enabled.
    """
    if not current_user and not getattr(
        app_settings, "allow_anonymous_analysis", False
    ):
        raise HTTPException(status_code=401, detail="Authentication required")

    session_id = str(uuid.uuid4())
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    is_pdf = "pdf" in content_type or filename.endswith(".pdf")
    file_type = "pdf" if is_pdf else "image"

    # Validate extension (best-effort; do not trust it alone)
    allowed_exts = set(getattr(app_settings, "allowed_extensions", []) or [])
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    if allowed_exts and ext and ext not in allowed_exts:
        raise HTTPException(status_code=415, detail="Unsupported file extension")

    # Validate size
    if len(raw) > int(app_settings.max_upload_size):
        raise HTTPException(status_code=413, detail="File too large")

    # Validate magic bytes / actual content (do not rely on Content-Type)
    if is_pdf:
        if not raw.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
    else:
        try:
            with Image.open(BytesIO(raw)) as img:
                img.verify()  # raises if corrupt/invalid
                if img.format not in {"JPEG", "PNG"}:
                    raise HTTPException(
                        status_code=415, detail="Unsupported image format"
                    )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")

    agent = VisionAgent()
    result = await agent.analyze_document(
        image_data={
            "file_type": file_type,
            "file_size": len(raw),
            "image_bytes": raw,
            "filename": file.filename,
            "content_type": file.content_type,
        },
        session_id=session_id,
    )

    return result
