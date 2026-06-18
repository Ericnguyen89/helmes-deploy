#!/usr/bin/env bash
# =============================================================================
# Helmes Agent - Deployment Script
# Ubuntu 22.04 / 4 cores / 8GB RAM
#
# Usage:
#   ./deploy.sh              Full install & start
#   ./deploy.sh link         Link Signal device (QR code)
#   ./deploy.sh register     Register new Signal number
#   ./deploy.sh status       Show service status
#   ./deploy.sh logs         Tail all logs
#   ./deploy.sh restart      Restart all services
#   ./deploy.sh stop         Stop all services
#   ./deploy.sh uninstall    Remove containers & images (keeps data)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

banner() {
    echo -e "${BLUE}"
    cat << 'EOF'
  _   _      _
 | | | | ___| |_ __ ___   ___  ___
 | |_| |/ _ \ | '_ ` _ \ / _ \/ __|
 |  _  |  __/ | | | | | |  __/\__ \
 |_| |_|\___|_|_| |_| |_|\___||___/
                            Agent

  Signal + AI Agent Deployment
EOF
    echo -e "${NC}"
}

# =============================================================================
# Pre-flight checks
# =============================================================================
check_system() {
    log_step "Checking system requirements..."

    if [[ "$(uname)" != "Linux" ]]; then
        log_error "This script is designed for Linux (Ubuntu 22.04)"
        exit 1
    fi

    local mem_kb
    mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local mem_gb=$((mem_kb / 1024 / 1024))
    if [[ $mem_gb -lt 2 ]]; then
        log_warn "Low RAM detected: ${mem_gb}GB (recommended: 4GB+)"
    else
        log_info "RAM: ${mem_gb}GB - OK"
    fi

    local disk_avail
    disk_avail=$(df -BG "$SCRIPT_DIR" | tail -1 | awk '{print $4}' | tr -d 'G')
    if [[ $disk_avail -lt 5 ]]; then
        log_warn "Low disk space: ${disk_avail}GB available (recommended: 10GB+)"
    else
        log_info "Disk: ${disk_avail}GB available - OK"
    fi

    local cores
    cores=$(nproc)
    log_info "CPU cores: ${cores}"
}

# =============================================================================
# Docker installation
# =============================================================================
install_docker() {
    if command -v docker &>/dev/null; then
        local docker_ver
        docker_ver=$(docker --version | head -1)
        log_info "Docker already installed: $docker_ver"
        return 0
    fi

    log_step "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release

    sudo install -m 0755 -d /etc/apt/keyrings
    if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
    fi

    if [[ ! -f /etc/apt/sources.list.d/docker.list ]]; then
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    fi

    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    if ! groups "$USER" | grep -q docker; then
        sudo usermod -aG docker "$USER"
        log_warn "Added $USER to docker group. You may need to log out/in or run: newgrp docker"
    fi

    sudo systemctl enable docker
    sudo systemctl start docker
    log_info "Docker installed successfully"
}

# =============================================================================
# Environment setup
# =============================================================================
setup_env() {
    if [[ -f .env ]]; then
        log_info ".env file already exists, skipping setup"
        return 0
    fi

    log_step "Setting up environment variables..."
    cp .env.example .env

    echo ""
    echo -e "${CYAN}Please provide the following configuration:${NC}"
    echo ""

    read -rp "  Signal phone number (e.g., +84901234567): " phone_number
    if [[ -n "$phone_number" ]]; then
        sed -i "s|SIGNAL_PHONE_NUMBER=.*|SIGNAL_PHONE_NUMBER=${phone_number}|" .env
        sed -i "s|ADMIN_NUMBERS=.*|ADMIN_NUMBERS=${phone_number}|" .env
    fi

    read -rp "  Anthropic API key (sk-ant-...): " api_key
    if [[ -n "$api_key" ]]; then
        sed -i "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${api_key}|" .env
    fi

    echo ""
    log_info ".env file created. You can edit it later: nano $SCRIPT_DIR/.env"
}

# =============================================================================
# Directory setup
# =============================================================================
setup_dirs() {
    log_step "Creating data directories..."
    mkdir -p data/signal-cli data/agent
    log_info "Data directories ready"
}

# =============================================================================
# Build & Start
# =============================================================================
build_and_start() {
    log_step "Building and starting services..."
    docker compose build --quiet
    docker compose up -d
    log_info "Services started"
}

# =============================================================================
# Wait for health
# =============================================================================
wait_for_health() {
    log_step "Waiting for services to be ready..."

    local max_wait=60
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        if curl -sf http://127.0.0.1:8080/v1/health &>/dev/null; then
            log_info "Signal API is healthy"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        printf "."
    done
    echo ""
    log_warn "Signal API not responding after ${max_wait}s (may need registration)"
}

# =============================================================================
# Signal device linking
# =============================================================================
link_device() {
    log_step "Linking Signal device..."
    echo ""
    echo -e "${YELLOW}To link this agent as a secondary Signal device:${NC}"
    echo ""
    echo "  1. Open Signal on your phone"
    echo "  2. Go to Settings > Linked Devices > Link New Device"
    echo "  3. The QR code data will appear below"
    echo ""

    if ! curl -sf http://127.0.0.1:8080/v1/health &>/dev/null; then
        log_error "Signal API is not running. Run './deploy.sh' first."
        exit 1
    fi

    local device_name="helmes-agent"
    echo -e "${CYAN}Generating QR code link...${NC}"
    echo ""

    local qr_link
    qr_link=$(curl -sf "http://127.0.0.1:8080/v1/qrcodelink?device_name=${device_name}" \
        -H "Content-Type: application/json")

    if [[ -n "$qr_link" ]]; then
        echo "$qr_link" | head -c 2000
        echo ""
        echo ""
        echo -e "${YELLOW}If you see a URI starting with 'sgnl://' above:${NC}"
        echo "  - You can generate a QR image from it using any QR generator"
        echo "  - Or open this URL in your browser for the QR code image:"
        echo "    http://YOUR_SERVER_IP:8080/v1/qrcodelink?device_name=${device_name}"
        echo ""
        echo -e "${GREEN}After scanning, restart the agent:${NC}"
        echo "  ./deploy.sh restart"
    else
        echo ""
        echo "  Try opening in your browser:"
        echo "  http://YOUR_SERVER_IP:8080/v1/qrcodelink?device_name=${device_name}"
        echo ""
        log_warn "Could not get QR code via CLI. Use the browser URL above."
    fi
}

# =============================================================================
# Signal number registration
# =============================================================================
register_number() {
    log_step "Registering new Signal number..."

    if ! curl -sf http://127.0.0.1:8080/v1/health &>/dev/null; then
        log_error "Signal API is not running. Run './deploy.sh' first."
        exit 1
    fi

    source .env 2>/dev/null || true
    local phone="${SIGNAL_PHONE_NUMBER:-}"
    if [[ -z "$phone" ]]; then
        read -rp "  Phone number to register (e.g., +84901234567): " phone
    fi

    echo ""
    echo -e "${YELLOW}Step 1: Get a captcha${NC}"
    echo "  Open this URL in your browser:"
    echo "  https://signalcaptchas.org/registration/generate.html"
    echo "  Complete the captcha and copy the token"
    echo ""

    read -rp "  Paste captcha token: " captcha

    echo ""
    log_info "Sending registration request for $phone..."

    local result
    result=$(curl -sf -X POST "http://127.0.0.1:8080/v1/register/${phone}" \
        -H "Content-Type: application/json" \
        -d "{\"captcha\": \"${captcha}\", \"use_voice\": false}" 2>&1) || true

    echo "  API response: $result"
    echo ""

    read -rp "  Enter SMS verification code: " verify_code

    local verify_result
    verify_result=$(curl -sf -X POST "http://127.0.0.1:8080/v1/register/${phone}/verify/${verify_code}" 2>&1) || true
    echo "  Verification response: $verify_result"

    echo ""
    log_info "Registration complete. Restarting services..."
    docker compose restart
}

# =============================================================================
# Status
# =============================================================================
show_status() {
    echo ""
    log_step "Service Status"
    echo ""
    docker compose ps
    echo ""

    if curl -sf http://127.0.0.1:8080/v1/health &>/dev/null; then
        echo -e "  Signal API:    ${GREEN}HEALTHY${NC}"
    else
        echo -e "  Signal API:    ${RED}NOT REACHABLE${NC}"
    fi

    if docker compose ps helmes-agent 2>/dev/null | grep -q "running"; then
        echo -e "  Helmes Agent:  ${GREEN}RUNNING${NC}"
    else
        echo -e "  Helmes Agent:  ${RED}NOT RUNNING${NC}"
    fi
    echo ""
}

# =============================================================================
# Logs
# =============================================================================
show_logs() {
    docker compose logs -f --tail=100
}

# =============================================================================
# Restart
# =============================================================================
do_restart() {
    log_step "Restarting services..."
    docker compose restart
    log_info "Services restarted"
    show_status
}

# =============================================================================
# Stop
# =============================================================================
do_stop() {
    log_step "Stopping services..."
    docker compose down
    log_info "Services stopped"
}

# =============================================================================
# Uninstall
# =============================================================================
do_uninstall() {
    echo -e "${RED}This will remove containers and images (data in ./data/ is preserved)${NC}"
    read -rp "Are you sure? (y/N): " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        log_info "Cancelled"
        return
    fi
    docker compose down --rmi all
    log_info "Containers and images removed. Data preserved in ./data/"
}

# =============================================================================
# Full deploy
# =============================================================================
full_deploy() {
    banner
    check_system
    install_docker
    setup_dirs
    setup_env
    build_and_start
    wait_for_health

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Helmes Agent deployed successfully!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "  ${CYAN}Next steps:${NC}"
    echo ""
    echo "  1. Link your Signal device:"
    echo "     ./deploy.sh link"
    echo ""
    echo "  2. Or register a new number:"
    echo "     ./deploy.sh register"
    echo ""
    echo "  3. After linking/registration, restart:"
    echo "     ./deploy.sh restart"
    echo ""
    echo "  4. Send a message to your Signal number to test!"
    echo ""
    echo -e "  ${CYAN}Management commands:${NC}"
    echo "     ./deploy.sh status    - Check service health"
    echo "     ./deploy.sh logs      - View live logs"
    echo "     ./deploy.sh restart   - Restart services"
    echo "     ./deploy.sh stop      - Stop services"
    echo ""
}

# =============================================================================
# Main
# =============================================================================
case "${1:-}" in
    link)       link_device ;;
    register)   register_number ;;
    status)     show_status ;;
    logs)       show_logs ;;
    restart)    do_restart ;;
    stop)       do_stop ;;
    uninstall)  do_uninstall ;;
    *)          full_deploy ;;
esac
