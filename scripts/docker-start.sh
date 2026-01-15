#!/bin/bash

# =============================================================================
# MedSafe - Script de Inicialização Docker (Padronizado)
# PHASE 1: Standardized startup script
# =============================================================================

set -e  # Exit on error

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Version
VERSION="2.0.0"

# =============================================================================
# FUNCTIONS
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}           🏥 ${GREEN}MedSafe - Docker Startup Script${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                    Version: ${VERSION}                       ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📌 $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 not found. Please install it first."
        return 1
    fi
    return 0
}

wait_for_service() {
    local service_name=$1
    local max_wait=$2
    local check_cmd=$3
    local counter=0
    
    echo -n "   ${service_name}: "
    
    while [ $counter -lt $max_wait ]; do
        if eval "$check_cmd" &> /dev/null; then
            echo -e "${GREEN}✅ Ready${NC}"
            return 0
        fi
        sleep 2
        counter=$((counter + 2))
        echo -n "."
    done
    
    echo -e "${RED}❌ Timeout${NC}"
    return 1
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

print_header
cd "$PROJECT_DIR"

# Step 1: Check Dependencies
log_step "Step 1/7: Checking dependencies..."

check_command docker || exit 1
log_info "Docker OK ($(docker --version | cut -d' ' -f3 | tr -d ','))"

# Detect docker compose command
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    check_command docker-compose || exit 1
    DOCKER_COMPOSE="docker-compose"
fi
log_info "Docker Compose OK"

# Check Docker daemon
if ! docker ps &> /dev/null; then
    log_error "Docker daemon is not running!"
    exit 1
fi

# Step 2: Environment Configuration
log_step "Step 2/7: Configuring environment..."

if [ ! -f ".env" ]; then
    log_warn ".env file not found"
    
    if [ -f "env.example" ]; then
        cp env.example .env
        log_info "Created .env from env.example"
        
        # Auto-generate secrets if python3 available
        if command -v python3 &> /dev/null; then
            SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
            JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
            POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')
            
            # Update .env with secrets (macOS compatible)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s/CHANGE_ME_GENERATE_WITH_SECRETS_MODULE_MIN_32_CHARS/$SECRET_KEY/g" .env 2>/dev/null || true
                sed -i '' "s/CHANGE_ME_GENERATE_RANDOM_PASSWORD/$POSTGRES_PASSWORD/g" .env 2>/dev/null || true
            else
                sed -i "s/CHANGE_ME_GENERATE_WITH_SECRETS_MODULE_MIN_32_CHARS/$SECRET_KEY/g" .env 2>/dev/null || true
                sed -i "s/CHANGE_ME_GENERATE_RANDOM_PASSWORD/$POSTGRES_PASSWORD/g" .env 2>/dev/null || true
            fi
            
            log_info "Secrets auto-generated"
        else
            log_warn "Python3 not found - please configure secrets manually in .env"
        fi
    else
        log_error "env.example not found!"
        exit 1
    fi
else
    log_info ".env file found"
fi

# Step 3: Create Required Directories
log_step "Step 3/7: Creating directories..."

mkdir -p logs data static/uploads frontend
log_info "Directories created"

# Step 4: Network Conflict Check
log_step "Step 4/7: Checking for network conflicts..."

MEDSAFE_SUBNET="172.22.0.0/16"
CONFLICT_NET=""

for net in $(docker network ls --format "{{.Name}}" | grep -v "medsafe" | grep -v "bridge\|host\|none"); do
    SUBNET=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "")
    if [ "$SUBNET" = "$MEDSAFE_SUBNET" ]; then
        CONFLICT_NET="$net"
        break
    fi
done

if [ -n "$CONFLICT_NET" ]; then
    log_error "Network conflict detected: $CONFLICT_NET uses $MEDSAFE_SUBNET"
    echo ""
    echo "Solutions:"
    echo "  1. Remove conflicting network: docker network rm $CONFLICT_NET"
    echo "  2. Run cleanup script: ./scripts/docker-clean-networks.sh"
    echo "  3. Modify subnet in docker-compose.yml"
    exit 1
fi
log_info "No network conflicts detected"

# Step 5: Stop Existing Containers
log_step "Step 5/7: Stopping existing containers..."

if docker ps -a | grep -q "medsafe"; then
    $DOCKER_COMPOSE down --remove-orphans 2>/dev/null || true
    log_info "Old containers removed"
else
    log_info "No existing containers"
fi

# Step 6: Build and Start
log_step "Step 6/7: Building and starting containers..."

# Build with retry
BUILD_SUCCESS=false
MAX_RETRIES=3

for i in $(seq 1 $MAX_RETRIES); do
    log_info "Build attempt $i of $MAX_RETRIES..."
    
    if $DOCKER_COMPOSE build; then
        BUILD_SUCCESS=true
        log_info "Build successful"
        break
    else
        if [ $i -lt $MAX_RETRIES ]; then
            log_warn "Build failed, retrying in 5s..."
            sleep 5
        fi
    fi
done

if [ "$BUILD_SUCCESS" = false ]; then
    log_error "Build failed after $MAX_RETRIES attempts"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check internet connection"
    echo "  - Run: docker login"
    echo "  - Run: ./scripts/docker-troubleshoot.sh"
    exit 1
fi

# Start containers
log_info "Starting services..."
$DOCKER_COMPOSE up -d

# Step 7: Wait for Services
log_step "Step 7/7: Waiting for services..."

wait_for_service "PostgreSQL" 60 "docker exec medsafe_db pg_isready -U medsafe"
wait_for_service "Ollama" 60 "docker exec medsafe_ollama ollama list"
wait_for_service "API" 90 "curl -sf http://localhost:9001/healthz"

# Download Ollama models if needed
log_info "Checking Ollama models..."
if ! docker exec medsafe_ollama ollama list 2>/dev/null | grep -q "qwen"; then
    log_warn "Downloading Ollama models (this may take a while)..."
    docker exec medsafe_ollama ollama pull qwen2.5:7b || true
    docker exec medsafe_ollama ollama pull qwen2.5vl:7b || true
    log_info "Models downloaded"
else
    log_info "Ollama models already available"
fi

# =============================================================================
# SUCCESS OUTPUT
# =============================================================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}        ✅ ${GREEN}MedSafe Started Successfully!${NC}                  ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}📍 Available URLs:${NC}"
echo "   🌐 Web Interface:    http://localhost:9001"
echo "   📚 API Docs:         http://localhost:9001/docs"
echo "   📖 ReDoc:            http://localhost:9001/redoc"
echo "   💚 Health Check:     http://localhost:9001/healthz"
echo "   📊 Metrics:          http://localhost:9001/metrics"
echo ""
echo -e "${CYAN}📊 Container Status:${NC}"
$DOCKER_COMPOSE ps
echo ""
echo -e "${CYAN}📝 Useful Commands:${NC}"
echo "   View all logs:       $DOCKER_COMPOSE logs -f"
echo "   View API logs:       $DOCKER_COMPOSE logs -f api"
echo "   Stop all:            $DOCKER_COMPOSE down"
echo "   Restart API:         $DOCKER_COMPOSE restart api"
echo ""
echo -e "${YELLOW}💡 Tip: Use '$DOCKER_COMPOSE logs -f api' to monitor in real-time${NC}"
echo ""
