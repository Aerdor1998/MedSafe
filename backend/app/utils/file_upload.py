"""
Upload seguro de arquivos com validação robusta.

SECURITY: Este módulo implementa validações críticas para prevenir:
- Path traversal attacks
- File type spoofing
- Polyglot files (arquivos maliciosos disfarçados)
- DoS via arquivos grandes

Compliance: OWASP File Upload Security
"""

import hashlib
import logging
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import PyPDF2
from fastapi import HTTPException, UploadFile
from PIL import Image

from ..config import settings

logger = logging.getLogger(__name__)


class FileValidationError(Enum):
    """Tipos de erro de validação de arquivo."""

    EMPTY_FILE = "empty_file"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_EXTENSION = "invalid_extension"
    INVALID_MAGIC_BYTES = "invalid_magic_bytes"
    INVALID_CONTENT = "invalid_content"
    FILENAME_UNSAFE = "filename_unsafe"
    PDF_MALFORMED = "pdf_malformed"
    IMAGE_MALFORMED = "image_malformed"
    PDF_TOO_MANY_PAGES = "pdf_too_many_pages"
    IMAGE_TOO_LARGE = "image_too_large"


@dataclass
class ValidationResult:
    """Resultado da validação de arquivo."""

    valid: bool
    mime_type: Optional[str] = None
    error: Optional[FileValidationError] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Magic bytes para detecção de tipo de arquivo
# Ref: https://en.wikipedia.org/wiki/List_of_file_signatures
MAGIC_BYTES = {
    # JPEG: FFD8FF + variações de marcador APP
    "image/jpeg": [
        (b"\xff\xd8\xff\xe0", "JFIF"),  # JFIF standard
        (b"\xff\xd8\xff\xe1", "EXIF"),  # EXIF (câmeras)
        (b"\xff\xd8\xff\xe2", "ICC"),  # ICC profile
        (b"\xff\xd8\xff\xe8", "SPIFF"),  # SPIFF
        (b"\xff\xd8\xff\xdb", "Raw"),  # Raw JPEG
        (b"\xff\xd8\xff\xee", "Adobe"),  # Adobe
    ],
    # PNG: signature completa
    "image/png": [
        (b"\x89PNG\r\n\x1a\n", "PNG"),
    ],
    # PDF: header + verificação de estrutura
    "application/pdf": [
        (b"%PDF-1.", "PDF 1.x"),
        (b"%PDF-2.", "PDF 2.x"),
    ],
}


class SecureFileUpload:
    """
    Classe para upload seguro de arquivos.

    SECURITY: Implementa validação em múltiplas camadas:
    1. Tamanho do arquivo
    2. Extensão do filename
    3. Magic bytes (assinatura do arquivo)
    4. Validação de estrutura (parsing real do arquivo)
    5. Limites de conteúdo (páginas PDF, dimensões de imagem)
    """

    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}

    @classmethod
    def get_max_file_size(cls) -> int:
        """Retorna tamanho máximo configurado."""
        return int(settings.max_upload_size)

    @classmethod
    def get_allowed_extensions(cls) -> set:
        """Retorna extensões permitidas configuradas."""
        configured = getattr(settings, "allowed_extensions", None)
        if configured:
            if isinstance(configured, str):
                return {f".{ext.strip().lower()}" for ext in configured.split(",")}
            return {f".{ext.lower()}" for ext in configured}
        return cls.ALLOWED_EXTENSIONS

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitiza nome do arquivo removendo caracteres perigosos.

        SECURITY: Previne path traversal e injection attacks.

        Args:
            filename: Nome do arquivo original

        Returns:
            Nome sanitizado

        Raises:
            HTTPException: Se o filename for inválido
        """
        if not filename:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "filename_required",
                    "message": "Nome do arquivo é obrigatório",
                },
            )

        # Remover path traversal
        safe_name = Path(filename).name

        # Validar que não contém caracteres perigosos
        if not safe_name or ".." in safe_name or "/" in safe_name or "\\" in safe_name:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "filename_unsafe",
                    "message": "Nome do arquivo contém caracteres não permitidos",
                },
            )

        # Limitar tamanho do filename
        if len(safe_name) > 255:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "filename_too_long",
                    "message": "Nome do arquivo muito longo (máximo 255 caracteres)",
                },
            )

        # Permitir apenas caracteres alfanuméricos, ponto e underscore
        import re

        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", safe_name)

        return safe_name

    @staticmethod
    def _detect_mime_by_magic(
        file_content: bytes,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Detecta MIME type por magic bytes.

        Args:
            file_content: Conteúdo do arquivo

        Returns:
            Tuple (mime_type, variant) ou (None, None) se não reconhecido
        """
        for mime_type, signatures in MAGIC_BYTES.items():
            for signature, variant in signatures:
                if file_content.startswith(signature):
                    return mime_type, variant

        # Fallback para JPEG com variação de marcador
        if file_content[:2] == b"\xff\xd8":
            return "image/jpeg", "Unknown variant"

        return None, None

    @staticmethod
    def validate_file_type(file_content: bytes) -> str:
        """
        Valida tipo do arquivo por magic bytes.

        SECURITY: Não confiar em Content-Type header ou extensão.
        Valida o conteúdo real do arquivo.

        Args:
            file_content: Conteúdo do arquivo em bytes

        Returns:
            MIME type validado

        Raises:
            HTTPException: Se o tipo não for permitido
        """
        # Verificar arquivo vazio
        if not file_content:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "empty_file",
                    "message": "Arquivo está vazio",
                },
            )

        # Verificar tamanho
        max_size = SecureFileUpload.get_max_file_size()
        if len(file_content) > max_size:
            size_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "file_too_large",
                    "message": f"Arquivo muito grande. Tamanho máximo: {size_mb:.1f}MB",
                    "max_size_bytes": max_size,
                    "file_size_bytes": len(file_content),
                },
            )

        # Detectar tipo por magic bytes
        mime_type, variant = SecureFileUpload._detect_mime_by_magic(file_content)

        if not mime_type:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_magic_bytes",
                    "message": "Tipo de arquivo não reconhecido. Permitidos: JPEG, PNG, PDF",
                    "hint": "Verifique se o arquivo não está corrompido",
                },
            )

        if mime_type not in SecureFileUpload.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=415,
                detail={
                    "error": "unsupported_type",
                    "message": f"Tipo de arquivo não suportado: {mime_type}",
                    "allowed_types": list(SecureFileUpload.ALLOWED_MIME_TYPES),
                },
            )

        logger.debug(f"File type validated: {mime_type} ({variant})")
        return mime_type

    @staticmethod
    def validate_extension(filename: str) -> str:
        """
        Valida extensão do arquivo.

        Args:
            filename: Nome do arquivo

        Returns:
            Extensão validada (lowercase, com ponto)

        Raises:
            HTTPException: Se extensão não permitida
        """
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "missing_extension",
                    "message": "Arquivo deve ter uma extensão válida",
                },
            )

        ext = "." + filename.rsplit(".", 1)[-1].lower()
        allowed = SecureFileUpload.get_allowed_extensions()

        if ext not in allowed:
            raise HTTPException(
                status_code=415,
                detail={
                    "error": "invalid_extension",
                    "message": f"Extensão '{ext}' não permitida",
                    "allowed_extensions": list(allowed),
                },
            )

        return ext

    @staticmethod
    def validate_image(file_content: bytes) -> None:
        """
        Valida que o arquivo é uma imagem válida

        Args:
            file_content: Conteúdo do arquivo

        Raises:
            HTTPException: Se a imagem for inválida
        """
        try:
            from io import BytesIO

            img = Image.open(BytesIO(file_content))
            img.verify()

            # Verificar dimensões máximas
            if img.size[0] > 10000 or img.size[1] > 10000:
                raise HTTPException(400, "Image dimensions too large (max 10000x10000)")

        except Exception as e:
            raise HTTPException(400, f"Invalid image file: {str(e)}")

    @staticmethod
    def validate_pdf(file_content: bytes) -> None:
        """
        Valida que o arquivo é um PDF válido

        Args:
            file_content: Conteúdo do arquivo

        Raises:
            HTTPException: Se o PDF for inválido
        """
        try:
            from io import BytesIO

            pdf = PyPDF2.PdfReader(BytesIO(file_content))

            # Verificar número de páginas
            if len(pdf.pages) > 50:
                raise HTTPException(400, "PDF has too many pages (max 50)")

        except Exception as e:
            raise HTTPException(400, f"Invalid PDF file: {str(e)}")

    @staticmethod
    async def save_upload_file(
        file: UploadFile, destination_dir: Optional[Path] = None
    ) -> Path:
        """
        Salva arquivo de upload de forma segura

        Args:
            file: Arquivo uploadado
            destination_dir: Diretório de destino (opcional)

        Returns:
            Path do arquivo salvo
        """
        # Ler conteúdo
        content = await file.read()

        # Sanitizar nome
        safe_filename = SecureFileUpload.sanitize_filename(file.filename)

        # Validar tipo
        mime_type = SecureFileUpload.validate_file_type(content)

        # Validar conteúdo baseado no tipo
        if mime_type.startswith("image/"):
            SecureFileUpload.validate_image(content)
        elif mime_type == "application/pdf":
            SecureFileUpload.validate_pdf(content)

        # Gerar hash do conteúdo para nome único
        file_hash = hashlib.sha256(content).hexdigest()[:16]

        # Criar nome final
        final_filename = f"{file_hash}_{safe_filename}"

        # Salvar em diretório temporário seguro
        if destination_dir is None:
            destination_dir = Path(tempfile.gettempdir()) / "medsafe_uploads"
            destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        file_path = destination_dir / final_filename

        # Salvar com permissões restritas
        file_path.write_bytes(content)
        file_path.chmod(0o600)  # Apenas owner pode ler/escrever

        return file_path
