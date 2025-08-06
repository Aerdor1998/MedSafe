#!/usr/bin/env python3
"""
Script para configurar modelos Ollama necessários para o MedSafe
"""

import subprocess
import sys
import time
import requests

def check_ollama_installed():
    """Verificar se o Ollama está instalado"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama está instalado")
            return True
        else:
            print("❌ Ollama não está instalado")
            return False
    except FileNotFoundError:
        print("❌ Ollama não encontrado")
        return False

def check_ollama_running():
    """Verificar se o Ollama está rodando"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama está rodando")
            return True
        else:
            print("❌ Ollama não está respondendo")
            return False
    except requests.exceptions.RequestException:
        print("❌ Ollama não está rodando")
        return False

def start_ollama():
    """Tentar iniciar o Ollama"""
    print("🚀 Tentando iniciar o Ollama...")
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)  # Aguardar inicialização
        return check_ollama_running()
    except Exception as e:
        print(f"❌ Erro ao iniciar Ollama: {e}")
        return False

def pull_model(model_name):
    """Baixar modelo do Ollama"""
    print(f"📥 Baixando modelo {model_name}...")
    try:
        result = subprocess.run(["ollama", "pull", model_name], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Modelo {model_name} baixado com sucesso")
            return True
        else:
            print(f"❌ Erro ao baixar {model_name}: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Erro ao baixar {model_name}: {e}")
        return False

def check_model_exists(model_name):
    """Verificar se o modelo já existe"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            for model in models:
                if model_name in model.get("name", ""):
                    print(f"✅ Modelo {model_name} já está disponível")
                    return True
            return False
        else:
            return False
    except Exception as e:
        print(f"❌ Erro ao verificar modelos: {e}")
        return False

def main():
    """Função principal"""
    print("=" * 60)
    print("🤖 Configurador de Modelos Ollama para MedSafe")
    print("=" * 60)
    
    # Modelos necessários
    required_models = [
        "qwen3:4b",      # Modelo de texto para análise geral
        "qwen2.5vl:7b"   # Modelo de visão para análise de imagens
    ]
    
    # 1. Verificar se Ollama está instalado
    if not check_ollama_installed():
        print("\n❌ Ollama não está instalado!")
        print("📝 Instale com:")
        print("   curl -fsSL https://ollama.com/install.sh | sh")
        print("   Ou acesse: https://ollama.com/download")
        sys.exit(1)
    
    # 2. Verificar se Ollama está rodando
    if not check_ollama_running():
        if not start_ollama():
            print("\n❌ Não foi possível iniciar o Ollama!")
            print("📝 Tente iniciar manualmente:")
            print("   ollama serve")
            sys.exit(1)
    
    # 3. Verificar e baixar modelos necessários
    print(f"\n📋 Verificando modelos necessários...")
    
    for model in required_models:
        print(f"\n🔍 Verificando {model}...")
        
        if not check_model_exists(model):
            print(f"📥 Modelo {model} não encontrado. Baixando...")
            
            if model == "qwen2.5vl:7b":
                print("⚠️  ATENÇÃO: Este modelo é grande (~4GB) e pode demorar para baixar")
                print("💡 O modelo de visão é essencial para análise de imagens de medicamentos")
            
            if not pull_model(model):
                print(f"❌ Falha ao baixar {model}")
                print("🔄 Você pode tentar novamente mais tarde com:")
                print(f"   ollama pull {model}")
            else:
                print(f"✅ {model} configurado com sucesso!")
    
    # 4. Verificação final
    print("\n🔍 Verificação final dos modelos...")
    all_models_ready = True
    
    for model in required_models:
        if check_model_exists(model):
            print(f"✅ {model} - OK")
        else:
            print(f"❌ {model} - Não disponível")
            all_models_ready = False
    
    print("\n" + "=" * 60)
    if all_models_ready:
        print("🎉 Todos os modelos estão prontos!")
        print("🚀 Você pode iniciar o MedSafe agora:")
        print("   ./start.sh")
        print("   ou")
        print("   python run.py")
    else:
        print("⚠️  Alguns modelos não estão disponíveis")
        print("💡 O sistema funcionará com funcionalidade limitada")
        print("🔄 Execute este script novamente para tentar baixar os modelos restantes")
    
    print("\n📊 Uso esperado dos modelos:")
    print("• qwen3:4b - Análise de texto, contraindicações, interações")
    print("• qwen2.5vl:7b - Análise de imagens de medicamentos")
    print("=" * 60)

if __name__ == "__main__":
    main()