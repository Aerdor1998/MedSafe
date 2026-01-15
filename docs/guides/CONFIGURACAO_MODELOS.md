# Configuração dos Modelos Ollama para MedSafe

## 🤖 Modelos Utilizados

O MedSafe usa dois modelos específicos do Ollama para diferentes funcionalidades:

### 1. **Qwen3:4b** - Modelo de Texto Principal
- **Função**: Análise farmacológica, contraindicações, interações
- **Tamanho**: ~2.3GB
- **Uso**: Processamento de texto, análise de dados de pacientes, geração de recomendações

### 2. **Qwen2.5VL:7b** - Modelo de Visão
- **Função**: Análise de imagens de medicamentos
- **Tamanho**: ~4.1GB  
- **Uso**: OCR inteligente, identificação de medicamentos por imagem, extração de texto de embalagens

## 🔧 Configuração Automática

### Instalação Rápida
```bash
# 1. Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Configurar modelos automaticamente
python setup_ollama.py

# 3. Iniciar sistema
./start.sh
```

### Configuração Manual
```bash
# Iniciar Ollama
ollama serve

# Em outro terminal, baixar modelos
ollama pull qwen3:4b
ollama pull qwen2.5vl:7b

# Verificar instalação
ollama list
```

## ⚙️ Configurações Técnicas

### Modelo de Texto (qwen3:4b)
```python
CONFIGURACAO_TEXTO = {
    "model": "qwen3:4b",
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "api_type": "openai",
    "temperature": 0.3,    # Baixa para precisão médica
    "max_tokens": 2048,
    "top_p": 0.9
}
```

### Modelo de Visão (qwen2.5vl:7b)
```python
CONFIGURACAO_VISAO = {
    "model": "qwen2.5vl:7b", 
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "api_type": "openai",
    "temperature": 0.1,    # Muito baixa para OCR preciso
    "max_tokens": 1500
}
```

## 🎯 Funcionalidades por Modelo

### Qwen3:4b (Análise de Texto)
✅ **Análise de contraindicações**
- Processa dados do paciente
- Aplica diretrizes OMS/ANVISA
- Identifica fatores de risco

✅ **Análise de interações medicamentosas**
- Compara com medicamentos atuais
- Classifica tipos de interação
- Avalia gravidade dos riscos

✅ **Geração de recomendações**
- Cria orientações personalizadas
- Sugere monitoramento necessário
- Propõe alternativas quando aplicável

### Qwen2.5VL:7b (Análise de Imagens)
✅ **Identificação de medicamentos**
- Reconhece nomes comerciais
- Identifica princípios ativos
- Extrai informações de dosagem

✅ **OCR avançado**
- Lê texto em embalagens
- Processa bulas e rótulos
- Identifica informações de lote/validade

✅ **Validação de imagens**
- Confirma se é medicamento
- Avalia qualidade da imagem
- Sugere melhorias na captura

## 🔍 Monitoramento e Logs

### Verificação de Status
```bash
# Verificar se Ollama está rodando
curl http://localhost:11434/api/tags

# Verificar modelos instalados
ollama list

# Status via API MedSafe
curl http://localhost:8000/api/health
```

### Logs de Performance
O sistema registra automaticamente:
- Tempo de resposta dos modelos
- Taxa de sucesso do OCR
- Confiança das análises
- Uso de recursos (CPU/RAM)

## 🚨 Troubleshooting

### Problemas Comuns

**Ollama não inicia:**
```bash
# Verificar portas em uso
sudo netstat -tulpn | grep 11434

# Reiniciar serviço
pkill ollama
ollama serve
```

**Modelo não baixa:**
```bash
# Verificar espaço em disco
df -h

# Tentar download manual
ollama pull qwen3:4b --verbose
```

**IA de visão falha:**
```bash
# Testar modelo diretamente
ollama run qwen2.5vl:7b "Analise esta imagem"

# Verificar logs do sistema
tail -f logs/error_*.jsonl
```

### Fallbacks Automáticos

O sistema tem fallbacks integrados:

1. **Se qwen2.5vl:7b não disponível**: Usa Tesseract OCR tradicional
2. **Se qwen3:4b não disponível**: Usa análise baseada apenas no banco de dados
3. **Se Ollama offline**: Sistema funciona com funcionalidade limitada

## 📊 Requisitos de Sistema

### Mínimos
- **RAM**: 8GB (4GB para modelo + 4GB sistema)
- **Storage**: 10GB livres
- **CPU**: 4 cores (recomendado)
- **GPU**: Opcional (acelera processamento)

### Recomendados
- **RAM**: 16GB (melhor performance)
- **Storage**: 20GB livres (para logs e cache)
- **CPU**: 8 cores ou mais
- **GPU**: NVIDIA com CUDA (opcional)

## 🔐 Segurança e Privacidade

### Processamento Local
✅ **Todos os dados permanecem no seu computador**
✅ **Nenhuma informação é enviada para servidores externos**
✅ **Modelos rodam completamente offline**
✅ **Conformidade total com LGPD**

### Dados Sensíveis
- Informações de pacientes são processadas apenas localmente
- Imagens de medicamentos não saem do dispositivo
- Análises são feitas sem conexão com a internet
- Logs podem ser anonimizados automaticamente

## 📈 Otimização de Performance

### Para melhor velocidade:
```bash
# Usar GPU se disponível
OLLAMA_GPU=1 ollama serve

# Aumentar contexto se necessário
OLLAMA_NUM_PARALLEL=2 ollama serve
```

### Para economizar RAM:
```bash
# Limitar uso de memória
OLLAMA_MODELS_PATH=/path/to/ssd ollama serve
```

### Configurações avançadas:
```env
# No arquivo config.env
OLLAMA_KEEP_ALIVE=5m
OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_FLASH_ATTENTION=1
```

## 📞 Suporte

Para problemas específicos com os modelos:

1. **Verificar logs**: `logs/ai_service_*.jsonl`
2. **Testar modelos**: `python setup_ollama.py`
3. **Verificar recursos**: Monitor de sistema
4. **Documentação Ollama**: https://ollama.com/docs

---

**Nota**: Os modelos Qwen são especialmente adequados para análise farmacológica devido à sua precisão em contextos médicos e capacidade multilíngue (português/inglês).