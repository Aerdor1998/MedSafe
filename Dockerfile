FROM ubuntu:22.04

# Evitar prompts interativos durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências básicas e Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-venv \
    curl \
    git \
    tesseract-ocr \
    tesseract-ocr-por \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Instalar Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Configurar diretório de trabalho
WORKDIR /app

# Copiar arquivos da aplicação
COPY . .

# Criar e ativar ambiente virtual
RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Expor a porta da API
EXPOSE 7860

# Script de inicialização
CMD ["bash", "start_hf.sh"]
