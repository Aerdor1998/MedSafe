#!/usr/bin/env python3
"""
MedSafe - Launcher Script
Sistema de Contra-indicativos de Medicamentos
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def check_dependencies():
    """Verificar dependências do sistema"""
    print("Verificando dependências...")
    
    # Verificar Python
    if sys.version_info < (3, 8):
        print("Python 3.8+ é necessário")
        return False
    
    # Verificar Tesseract
    try:
        subprocess.run(["tesseract", "--version"], check=True, capture_output=True)
        print("Tesseract OCR encontrado")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Tesseract OCR não encontrado")
        print("   Instale com: sudo apt-get install tesseract-ocr tesseract-ocr-por")
        return False
    
    # Verificar Ollama
    try:
        subprocess.run(["ollama", "list"], check=True, capture_output=True)
        print("Ollama encontrado")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(" Ollama não encontrado - funcionalidade de IA será limitada")
        print("   Instale com: curl -fsSL https://ollama.com/install.sh | sh")
    
    return True

def install_python_deps():
    """Instalar dependências Python"""
    print("Instalando dependências Python...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        print("Dependências Python instaladas")
        return True
    except subprocess.CalledProcessError:
        print("Erro ao instalar dependências Python")
        return False

def setup_database():
    """Configurar banco de dados"""
    print("🗄️  Configurando banco de dados...")
    
    try:
        from app.db.database import init_db
        init_db()
        print("Banco de dados configurado")
        return True
    except Exception as e:
        print(f" Aviso ao configurar banco: {e}")
        print("   O banco será inicializado quando a aplicação iniciar")
        return True  # Continuar mesmo sem o banco configurado aqui

def start_server():
    """Iniciar servidor FastAPI"""
    # SKILL: debugging-strategies
    # FIX: Porta mudada 8000 → 9000 → 9001 (conflito de porta)
    print("Iniciando MedSafe...")
    print("📍 Acesse: http://localhost:9001")
    print("📍 Documentação: http://localhost:9001/docs")
    print("⏹️  Pressione Ctrl+C para parar")
    
    try:
        # Usar uvicorn para iniciar a aplicação
        # SKILL: debugging-strategies
        # FIX: Porta mudada para 9001
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "backend.app.main:app",
            "--host", "0.0.0.0",
            "--port", "9001",
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 MedSafe encerrado")
    except Exception as e:
        print(f"Erro ao iniciar servidor: {e}")

def main():
    """Função principal"""
    print("=" * 60)
    print("🏥 MedSafe - Sistema de Contra-indicativos de Medicamentos")
    print("   Baseado em diretrizes OMS e ANVISA")
    print("=" * 60)
    
    # Verificar dependências
    if not check_dependencies():
        print("\nDependências não atendidas. Verifique a instalação.")
        sys.exit(1)
    
    # Instalar dependências Python se necessário
    if not os.path.exists("backend/__pycache__"):
        if not install_python_deps():
            sys.exit(1)
    
    # Configurar banco de dados
    if not setup_database():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Sistema pronto!")
    print("📋 Funcionalidades:")
    print("   • Anamnese digital interativa")
    print("   • OCR para reconhecimento de medicamentos")
    print("   • Análise baseada em diretrizes OMS/ANVISA")
    print("   • Visualização 3D com Three.js")
    print("   • Processamento local (AG2/Ollama)")
    print("   • Auditoria para farmacovigilância")
    print("=" * 60)
    print()
    
    # Iniciar servidor
    start_server()

if __name__ == "__main__":
    main()