#!/bin/bash

# MedSafe Startup Script
# Sistema de Contra-indicativos de Medicamentos

echo "=========================================="
echo "🏥 MedSafe - Sistema de Contra-indicativos"
echo "   Baseado em diretrizes OMS e ANVISA"
echo "=========================================="

# Verificar se está no diretório correto
if [ ! -f "requirements.txt" ]; then
    echo "❌ Execute este script na raiz do projeto MedSafe"
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado"
    exit 1
fi

echo "✅ Python encontrado: $(python3 --version)"

# Verificar Tesseract
if ! command -v tesseract &> /dev/null; then
    echo "⚠️  Tesseract OCR não encontrado"
    echo "   Instale com: sudo apt-get install tesseract-ocr tesseract-ocr-por"
else
    echo "✅ Tesseract encontrado: $(tesseract --version | head -1)"
fi

# Verificar Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama não encontrado - funcionalidade de IA será limitada"
    echo "   Instale com: curl -fsSL https://ollama.com/install.sh | sh"
else
    echo "✅ Ollama encontrado"
    
    # Verificar se os modelos necessários estão instalados
    if ! ollama list | grep -q "qwen3:4b"; then
        echo "📥 Configurando modelos Ollama..."
        python setup_ollama.py
    fi
fi

# Criar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativar ambiente virtual
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Instalar dependências
echo "📦 Instalando dependências Python..."
pip install -r requirements.txt

# Criar diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p data logs static/uploads

# Configurar variáveis de ambiente
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

echo ""
echo "=========================================="
echo "✅ Sistema pronto!"
echo "📋 Funcionalidades:"
echo "   • Anamnese digital interativa"
echo "   • OCR para reconhecimento de medicamentos"
echo "   • Análise baseada em diretrizes OMS/ANVISA"
echo "   • Visualização 3D com Three.js"
echo "   • Processamento local (Ollama qwen3:4b + qwen2.5vl:7b)"
echo "   • Auditoria para farmacovigilância"
echo "=========================================="
echo ""
echo "🚀 Iniciando MedSafe..."
echo "📍 Acesse: http://localhost:8000"
echo "⏹️  Pressione Ctrl+C para parar"
echo ""

# Iniciar aplicação
cd backend
python main.py