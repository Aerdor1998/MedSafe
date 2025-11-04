"""
Upload seguro de arquivos
"""

import tempfile
from pathlib import Path
from typing import Optional
import hashlib
from fastapi import UploadFile, HTTPException
from PIL import Image
import PyPDF2


class SecureFileUpload:
    """Classe para upload seguro de arquivos"""

    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitiza nome do arquivo removendo caracteres perigosos

        Args:
            filename: Nome do arquivo original

        Returns:
            Nome sanitizado
        """
        # Remover path traversal
        safe_name = Path(filename).name

        # Validar que não contém caracteres perigosos
        if not safe_name or ".." in safe_name or "/" in safe_name:
            raise HTTPException(400, "Invalid filename")

        # Permitir apenas caracteres alfanuméricos, ponto e underscore
        import re

        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", safe_name)

        return safe_name

    @staticmethod
    def validate_file_type(file_content: bytes) -> str:
        """
        Valida tipo do arquivo por magic bytes

        Args:
            file_content: Conteúdo do arquivo em bytes

        Returns:
            MIME type validado

        Raises:
            HTTPException: Se o tipo não for permitido
        """
        # Verificar tamanho
        if len(file_content) > SecureFileUpload.MAX_FILE_SIZE:
            raise HTTPException(413, "File too large (max 10MB)")

        # Verificar magic bytes básicos
        mime_type = None

        # JPEG
        if file_content.startswith(b"\xff\xd8\xff"):
            mime_type = "image/jpeg"
        # PNG
        elif file_content.startswith(b"\x89PNG\r\n\x1a\n"):
            mime_type = "image/png"
        # PDF
        elif file_content.startswith(b"%PDF"):
            mime_type = "application/pdf"

        if not mime_type or mime_type not in SecureFileUpload.ALLOWED_MIME_TYPES:
            raise HTTPException(400, "Unsupported file type. Allowed: JPEG, PNG, PDF")

        return mime_type

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
