#!/bin/bash
set -e

# Iniciar o Ollama em segundo plano
ollama serve &

# Aguardar o Ollama iniciar
echo "Aguardando o Ollama iniciar..."
sleep 10

# Baixar os modelos necessários
echo "Baixando modelos Ollama (se necessário)..."
ollama pull qwen3:4b
ollama pull qwen2.5vl:7b

echo "Modelos prontos."

# Iniciar a aplicação FastAPI
echo "Iniciando a API MedSafe..."
cd backend
uvicorn main:app --host 0.0.0.0 --port 7860
