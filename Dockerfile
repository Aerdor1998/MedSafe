FROM python:3.10-slim

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Criar usuário não-privilegiado
RUN groupadd -r medsafe && useradd -r -g medsafe medsafe

# Configurar diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro (cache layer)
COPY requirements.txt ./

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY static/ ./static/

# Criar diretórios com permissões corretas
RUN mkdir -p logs data static/uploads && \
    chown -R medsafe:medsafe /app

# Mudar para usuário não-privilegiado
USER medsafe

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Usar uvicorn diretamente (melhor para produção)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
