#!/bin/bash

# ============================================================================
# MedSafe - Full Stack Start Script
# ============================================================================
# Unifica: Docker Start + Database Indexing + Monitoring Stack
#
# SKILLS: @deployment-pipeline-design, @prometheus-configuration, @debugging-strategies
#
# Usage:
#   ./scripts/medsafe-full-start.sh              # Start all (default)
#   ./scripts/medsafe-full-start.sh --no-monitoring   # Skip monitoring stack
#   ./scripts/medsafe-full-start.sh --no-indexes      # Skip database indexes
#   ./scripts/medsafe-full-start.sh --rebuild         # Force rebuild images
#   ./scripts/medsafe-full-start.sh --help            # Show help
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Defaults
ENABLE_MONITORING=true
ENABLE_INDEXES=true
FORCE_REBUILD=false
VERBOSE=false

# ============================================================================
# Parse Arguments
# ============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-monitoring)
                ENABLE_MONITORING=false
                shift
                ;;
            --no-indexes)
                ENABLE_INDEXES=false
                shift
                ;;
            --rebuild)
                FORCE_REBUILD=true
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    echo ""
    echo -e "${BOLD}${CYAN}MedSafe Full Stack Start${NC}"
    echo ""
    echo "Usage: ./scripts/medsafe-full-start.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --no-monitoring    Skip Prometheus + Grafana stack"
    echo "  --no-indexes       Skip database performance indexes"
    echo "  --rebuild          Force rebuild all Docker images"
    echo "  --verbose, -v      Show detailed output"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/medsafe-full-start.sh                  # Full start"
    echo "  ./scripts/medsafe-full-start.sh --no-monitoring  # Without monitoring"
    echo "  ./scripts/medsafe-full-start.sh --rebuild        # Force rebuild"
    echo ""
}

# ============================================================================
# Utility Functions
# ============================================================================
print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}============================================${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"
}

print_success() {
    echo -e "    ${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "    ${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "    ${RED}❌ $1${NC}"
}

print_info() {
    echo -e "    ${CYAN}ℹ️  $1${NC}"
}

# Detect docker compose command
detect_docker_compose() {
    if docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

DOCKER_COMPOSE=$(detect_docker_compose)

# Wait for service with spinner
wait_for_service() {
    local name=$1
    local max_wait=$2
    local check_cmd=$3
    local counter=0

    echo -n "    Waiting for $name: "

    while [ $counter -lt $max_wait ]; do
        if eval "$check_cmd" &> /dev/null; then
            echo -e "${GREEN}Ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        counter=$((counter + 2))
    done

    echo -e "${RED}Timeout!${NC}"
    return 1
}

# ============================================================================
# Main Steps
# ============================================================================

step_check_dependencies() {
    print_step 1 "Checking dependencies..."

    # Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found!"
        echo "      Install: https://docs.docker.com/get-docker/"
        exit 1
    fi
    print_success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

    # Docker running
    if ! docker ps &> /dev/null; then
        print_error "Docker daemon not running!"
        exit 1
    fi
    print_success "Docker daemon running"

    # Docker Compose
    if ! $DOCKER_COMPOSE version &> /dev/null; then
        print_error "Docker Compose not found!"
        exit 1
    fi
    print_success "Docker Compose available"
}

step_setup_environment() {
    print_step 2 "Setting up environment..."

    # Create directories
    mkdir -p logs data static/uploads frontend
    print_success "Directories created"

    # Check .env
    if [ ! -f ".env" ]; then
        if [ -f "env.example" ]; then
            cp env.example .env
            print_warning ".env created from env.example"
            print_info "Edit .env to configure secrets!"

            # Generate secrets if python available
            if command -v python3 &> /dev/null; then
                SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
                JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
                sed -i "s/CHANGE_ME_GENERATE_WITH_SECRETS_MODULE_MIN_32_CHARS/$SECRET_KEY/g" .env 2>/dev/null || true
                print_success "Secrets auto-generated"
            fi
        else
            print_error "env.example not found!"
            exit 1
        fi
    else
        print_success ".env found"
    fi
}

step_cleanup_old_containers() {
    print_step 3 "Cleaning up old containers..."

    if docker ps -a | grep -q "medsafe"; then
        $DOCKER_COMPOSE down --remove-orphans 2>/dev/null || true
        print_success "Old containers removed"
    else
        print_success "No old containers found"
    fi
}

step_check_network_conflicts() {
    print_step 4 "Checking network conflicts..."

    MEDSAFE_SUBNET="172.22.0.0/16"

    for net in $(docker network ls --format "{{.Name}}" | grep -v "medsafe\|bridge\|host\|none"); do
        SUBNET=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "")
        if [ "$SUBNET" = "$MEDSAFE_SUBNET" ]; then
            print_error "Network conflict: '$net' uses $MEDSAFE_SUBNET"
            print_info "Run: docker network rm $net"
            exit 1
        fi
    done

    print_success "No network conflicts"
}

step_build_and_start() {
    print_step 5 "Building and starting containers..."

    # Build
    BUILD_OPTS=""
    if [ "$FORCE_REBUILD" = true ]; then
        BUILD_OPTS="--no-cache"
        print_info "Force rebuild enabled"
    fi

    echo ""
    echo -e "    ${MAGENTA}Building images...${NC}"
    if $DOCKER_COMPOSE build $BUILD_OPTS; then
        print_success "Build completed"
    else
        print_error "Build failed!"
        exit 1
    fi

    # Start
    echo ""
    echo -e "    ${MAGENTA}Starting services...${NC}"
    $DOCKER_COMPOSE up -d
    print_success "Containers started"
}

step_wait_for_services() {
    print_step 6 "Waiting for services to be ready..."

    echo ""
    wait_for_service "PostgreSQL" 30 "docker exec medsafe_db pg_isready -U medsafe"
    wait_for_service "Ollama" 30 "docker exec medsafe_ollama ollama list"
    wait_for_service "API" 60 "curl -sf http://localhost:9001/healthz"
}

step_apply_indexes() {
    if [ "$ENABLE_INDEXES" = false ]; then
        print_step 7 "Skipping database indexes (--no-indexes)"
        return
    fi

    print_step 7 "Applying database performance indexes..."

    MIGRATION_FILE="$PROJECT_ROOT/backend/app/db/migrations/001_add_performance_indexes.sql"

    if [ ! -f "$MIGRATION_FILE" ]; then
        print_warning "Migration file not found, skipping indexes"
        return
    fi

    # Check if indexes already exist
    EXISTING=$(docker exec medsafe_db psql -U medsafe -d medsafe -t -c \
        "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_%'" 2>/dev/null | tr -d ' ')

    if [ "$EXISTING" -gt 10 ]; then
        print_success "Performance indexes already applied ($EXISTING indexes)"
    else
        echo ""
        echo -e "    ${MAGENTA}Applying performance indexes...${NC}"
        if docker exec -i medsafe_db psql -U medsafe -d medsafe < "$MIGRATION_FILE" > /dev/null 2>&1; then
            print_success "Performance indexes applied"
        else
            print_warning "Some indexes may already exist (this is OK)"
        fi
    fi
}

step_start_monitoring() {
    if [ "$ENABLE_MONITORING" = false ]; then
        print_step 8 "Skipping monitoring stack (--no-monitoring)"
        return
    fi

    print_step 8 "Starting monitoring stack (Prometheus + Grafana)..."

    # Check if monitoring compose exists
    if [ ! -f "docker-compose.monitoring.yml" ]; then
        print_warning "docker-compose.monitoring.yml not found, skipping"
        return
    fi

    # Create external network if needed
    if ! docker network ls | grep -q "medsafe_medsafe_network"; then
        docker network create medsafe_medsafe_network 2>/dev/null || true
    fi

    # Connect main containers to monitoring network
    docker network connect medsafe_medsafe_network medsafe_api 2>/dev/null || true
    docker network connect medsafe_medsafe_network medsafe_db 2>/dev/null || true
    docker network connect medsafe_medsafe_network medsafe_ollama 2>/dev/null || true

    echo ""
    echo -e "    ${MAGENTA}Starting Prometheus & Grafana...${NC}"

    if $DOCKER_COMPOSE -f docker-compose.monitoring.yml up -d 2>/dev/null; then
        print_success "Monitoring stack started"

        # Wait for Grafana
        echo ""
        wait_for_service "Prometheus" 30 "curl -sf http://localhost:9090/-/healthy"
        wait_for_service "Grafana" 30 "curl -sf http://localhost:3001/api/health"
    else
        print_warning "Monitoring stack failed to start (continuing without it)"
    fi
}

step_download_models() {
    print_step 9 "Checking Ollama models..."

    # Get model from .env
    OLLAMA_MODEL=$(grep "^OLLAMA_LLM=" .env 2>/dev/null | cut -d'=' -f2 || echo "llama3.2:3b")

    if docker exec medsafe_ollama ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}"; then
        print_success "Model $OLLAMA_MODEL already installed"
    else
        print_info "Downloading model $OLLAMA_MODEL (this may take a while)..."
        docker exec medsafe_ollama ollama pull "$OLLAMA_MODEL" || print_warning "Model download failed"
    fi
}

step_show_summary() {
    echo ""
    echo -e "${BOLD}${GREEN}============================================${NC}"
    echo -e "${BOLD}${GREEN}  MedSafe Started Successfully!${NC}"
    echo -e "${BOLD}${GREEN}============================================${NC}"
    echo ""

    echo -e "${BOLD}Core Services:${NC}"
    echo -e "  ${CYAN}Web Interface:${NC}    http://localhost:9001"
    echo -e "  ${CYAN}API Docs:${NC}         http://localhost:9001/docs"
    echo -e "  ${CYAN}Health Check:${NC}     http://localhost:9001/healthz"
    echo -e "  ${CYAN}Metrics:${NC}          http://localhost:9001/metrics"
    echo ""

    if [ "$ENABLE_MONITORING" = true ]; then
        echo -e "${BOLD}Monitoring:${NC}"
        echo -e "  ${CYAN}Prometheus:${NC}       http://localhost:9090"
        echo -e "  ${CYAN}Grafana:${NC}          http://localhost:3001"
        echo -e "  ${CYAN}  User/Pass:${NC}      admin / medsafe2025"
        echo ""
    fi

    echo -e "${BOLD}Containers Running:${NC}"
    $DOCKER_COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $DOCKER_COMPOSE ps
    echo ""

    if [ "$ENABLE_MONITORING" = true ] && [ -f "docker-compose.monitoring.yml" ]; then
        $DOCKER_COMPOSE -f docker-compose.monitoring.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
        echo ""
    fi

    echo -e "${BOLD}Quick Commands:${NC}"
    echo "  View logs:        docker-compose logs -f api"
    echo "  Stop all:         docker-compose down"
    echo "  Restart API:      docker-compose restart api"
    echo ""

    if [ "$ENABLE_MONITORING" = true ]; then
        echo "  Stop monitoring:  docker-compose -f docker-compose.monitoring.yml down"
        echo ""
    fi

    echo -e "${BOLD}${GREEN}Ready to use!${NC}"
    echo ""
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    parse_args "$@"

    # Calculate total steps
    TOTAL_STEPS=9

    print_header "MedSafe Full Stack Start"

    echo -e "${CYAN}Configuration:${NC}"
    echo "  Monitoring: $([ "$ENABLE_MONITORING" = true ] && echo "enabled" || echo "disabled")"
    echo "  Indexes:    $([ "$ENABLE_INDEXES" = true ] && echo "enabled" || echo "disabled")"
    echo "  Rebuild:    $([ "$FORCE_REBUILD" = true ] && echo "yes" || echo "no")"
    echo ""

    step_check_dependencies
    step_setup_environment
    step_cleanup_old_containers
    step_check_network_conflicts
    step_build_and_start
    step_wait_for_services
    step_apply_indexes
    step_start_monitoring
    step_download_models
    step_show_summary
}

# Run
main "$@"
