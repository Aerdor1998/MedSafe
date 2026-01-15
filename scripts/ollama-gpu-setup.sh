#!/bin/bash

# Ollama GPU Setup & Verification Script
# SKILL: @python-performance-optimization - GPU configuration for LLM performance
#
# This script:
# 1. Verifies GPU availability
# 2. Configures Ollama to use GPU with maximum capacity
# 3. Tests GPU acceleration
# 4. Provides performance benchmarks

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}🚀 MedSafe - Ollama GPU Setup${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# ============================================================================
# 1. Check GPU Availability
# ============================================================================

echo -e "${YELLOW}📊 Step 1/5: Checking GPU availability...${NC}"
echo ""

# Check NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✅ NVIDIA GPU detected${NC}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    echo -e "${GREEN}   Found ${GPU_COUNT} GPU(s)${NC}"

    # Get GPU memory
    GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
    echo -e "${GREEN}   GPU Memory: ${GPU_MEMORY} MB${NC}"

    HAS_GPU=true
else
    echo -e "${RED}❌ No NVIDIA GPU detected${NC}"
    echo -e "${YELLOW}   Ollama will run on CPU (slower performance)${NC}"
    HAS_GPU=false
fi

echo ""

# ============================================================================
# 2. Set Ollama Environment Variables for GPU
# ============================================================================

echo -e "${YELLOW}🔧 Step 2/5: Configuring Ollama for GPU...${NC}"
echo ""

if [ "$HAS_GPU" = true ]; then
    # Export Ollama GPU environment variables
    export OLLAMA_NUM_GPU=99              # Use all available GPUs
    export OLLAMA_GPU_LAYERS=99           # Load all layers to GPU
    export OLLAMA_MAX_LOADED_MODELS=2     # Keep 2 models in VRAM
    export OLLAMA_NUM_PARALLEL=4          # Parallel requests
    export OLLAMA_FLASH_ATTENTION=1       # Enable flash attention (faster)
    export OLLAMA_CUDA_VISIBLE_DEVICES=0  # Use first GPU (change if multiple)

    echo -e "${GREEN}✅ GPU environment variables set:${NC}"
    echo -e "   OLLAMA_NUM_GPU=99"
    echo -e "   OLLAMA_GPU_LAYERS=99"
    echo -e "   OLLAMA_MAX_LOADED_MODELS=2"
    echo -e "   OLLAMA_NUM_PARALLEL=4"
    echo -e "   OLLAMA_FLASH_ATTENTION=1"

    # Save to .env file for docker-compose
    ENV_FILE=".env"

    if [ -f "$ENV_FILE" ]; then
        # Backup existing .env
        cp "$ENV_FILE" "${ENV_FILE}.backup"
        echo -e "${GREEN}✅ Backed up existing .env to .env.backup${NC}"
    fi

    # Add/update GPU settings in .env
    cat >> "$ENV_FILE" << EOF

# Ollama GPU Configuration (added by ollama-gpu-setup.sh)
OLLAMA_NUM_GPU=99
OLLAMA_GPU_LAYERS=99
OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_NUM_PARALLEL=4
OLLAMA_FLASH_ATTENTION=1
OLLAMA_CUDA_VISIBLE_DEVICES=0
EOF

    echo -e "${GREEN}✅ GPU settings added to .env${NC}"
else
    echo -e "${YELLOW}⚠️  No GPU detected, skipping GPU configuration${NC}"
fi

echo ""

# ============================================================================
# 3. Check Ollama Status
# ============================================================================

echo -e "${YELLOW}🔍 Step 3/5: Checking Ollama status...${NC}"
echo ""

if docker ps | grep -q ollama; then
    echo -e "${GREEN}✅ Ollama container is running${NC}"

    # Check which models are loaded
    echo -e "${BLUE}📦 Loaded models:${NC}"
    docker exec ollama ollama list || echo "   No models found"
else
    echo -e "${RED}❌ Ollama container not running${NC}"
    echo -e "${YELLOW}   Starting Ollama with GPU support...${NC}"

    # Start Ollama with GPU support
    docker run -d \
        --gpus all \
        --name ollama \
        -p 11434:11434 \
        -v ollama:/root/.ollama \
        -e OLLAMA_NUM_GPU=99 \
        -e OLLAMA_GPU_LAYERS=99 \
        -e OLLAMA_MAX_LOADED_MODELS=2 \
        -e OLLAMA_NUM_PARALLEL=4 \
        -e OLLAMA_FLASH_ATTENTION=1 \
        ollama/ollama:latest

    echo -e "${GREEN}✅ Ollama started with GPU support${NC}"
    sleep 5
fi

echo ""

# ============================================================================
# 4. Pull and Configure Models with GPU
# ============================================================================

echo -e "${YELLOW}📥 Step 4/5: Pulling models with GPU configuration...${NC}"
echo ""

MODELS=("qwen2.5:7b" "qwen2.5vl:7b")

for model in "${MODELS[@]}"; do
    echo -e "${BLUE}Pulling $model...${NC}"
    docker exec ollama ollama pull "$model"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $model pulled successfully${NC}"
    else
        echo -e "${RED}❌ Failed to pull $model${NC}"
    fi
    echo ""
done

# ============================================================================
# 5. GPU Performance Test
# ============================================================================

echo -e "${YELLOW}⚡ Step 5/5: Testing GPU performance...${NC}"
echo ""

if [ "$HAS_GPU" = true ]; then
    echo -e "${BLUE}Running inference test...${NC}"

    # Test qwen2.5:7b with GPU
    START_TIME=$(date +%s)

    docker exec ollama ollama run qwen2.5:7b "What is the mechanism of action of aspirin? Be concise." --verbose &> /tmp/ollama_test.log

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo -e "${GREEN}✅ Test completed in ${DURATION} seconds${NC}"

    # Check if GPU was used
    if grep -q "gpu" /tmp/ollama_test.log; then
        echo -e "${GREEN}✅ GPU acceleration confirmed!${NC}"
    else
        echo -e "${YELLOW}⚠️  GPU may not be active (check logs)${NC}"
    fi

    # Show GPU utilization
    echo -e "${BLUE}GPU Utilization during test:${NC}"
    nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv,noheader
else
    echo -e "${YELLOW}⚠️  Skipping GPU test (no GPU available)${NC}"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✅ Ollama GPU Setup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

if [ "$HAS_GPU" = true ]; then
    echo -e "${GREEN}GPU Configuration Summary:${NC}"
    echo -e "  • GPU Count: ${GPU_COUNT}"
    echo -e "  • GPU Memory: ${GPU_MEMORY} MB"
    echo -e "  • All layers loaded to GPU (num_gpu=99)"
    echo -e "  • Flash Attention enabled"
    echo -e "  • Parallel requests: 4"
    echo ""
    echo -e "${BLUE}Expected Performance Improvement:${NC}"
    echo -e "  • 5-10x faster inference vs CPU"
    echo -e "  • Support for larger context windows"
    echo -e "  • Better throughput for parallel requests"
else
    echo -e "${YELLOW}⚠️  Running on CPU${NC}"
    echo -e "${YELLOW}   For GPU acceleration, ensure:${NC}"
    echo -e "${YELLOW}   1. NVIDIA GPU installed${NC}"
    echo -e "${YELLOW}   2. NVIDIA drivers installed${NC}"
    echo -e "${YELLOW}   3. Docker with --gpus support${NC}"
fi

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Restart MedSafe: ${GREEN}./scripts/docker-start.sh${NC}"
echo -e "  2. Check Ollama logs: ${GREEN}docker logs ollama${NC}"
echo -e "  3. Test analysis at: ${GREEN}http://localhost:9000${NC}"
echo ""

# Cleanup
rm -f /tmp/ollama_test.log
