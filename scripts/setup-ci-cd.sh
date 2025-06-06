#!/bin/bash
# Comprehensive CI/CD setup script for ProEthica

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    local missing=()
    
    # Check required commands
    for cmd in ssh ssh-keygen git; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    
    # Check docker and docker compose
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    elif ! docker compose version &> /dev/null; then
        missing+=("docker-compose")
    fi
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required commands: ${missing[*]}"
        exit 1
    fi
    
    # Check for .git directory
    if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
        error "Not in a git repository"
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Generate SSH keys
setup_ssh_keys() {
    log "Setting up SSH keys..."
    
    local ssh_key="$HOME/.ssh/proethica-deploy"
    
    if [[ -f "$ssh_key" ]]; then
        warning "SSH key already exists at $ssh_key"
        read -p "Regenerate? (yes/no): " regen
        if [[ "$regen" != "yes" ]]; then
            return 0
        fi
    fi
    
    ssh-keygen -t ed25519 -f "$ssh_key" -C "github-actions@proethica" -N ""
    
    success "SSH key generated at $ssh_key"
    
    # Show public key for manual setup
    echo ""
    echo "Add this public key to your server's authorized_keys:"
    echo "----------------------------------------"
    cat "${ssh_key}.pub"
    echo "----------------------------------------"
    echo ""
    
    read -p "Have you added the public key to the server? (yes/no): " added
    if [[ "$added" != "yes" ]]; then
        warning "Please add the public key to the server before continuing"
        return 1
    fi
    
    # Test connection
    local server_host="${DROPLET_HOST:-209.38.62.85}"
    local server_user="${DROPLET_USER:-chris}"
    
    if ssh -i "$ssh_key" -o ConnectTimeout=10 "${server_user}@${server_host}" "echo 'Connection test successful'"; then
        success "SSH connection test passed"
    else
        error "SSH connection test failed"
        return 1
    fi
}

# Set up GitHub secrets
setup_github_secrets() {
    log "Setting up GitHub secrets..."
    
    local ssh_key="$HOME/.ssh/proethica-deploy"
    
    if [[ ! -f "$ssh_key" ]]; then
        error "SSH key not found. Run setup_ssh_keys first."
        return 1
    fi
    
    echo ""
    echo "Add these secrets to your GitHub repository:"
    echo "Go to: Settings → Secrets and variables → Actions"
    echo ""
    
    echo "DROPLET_SSH_KEY:"
    echo "----------------------------------------"
    cat "$ssh_key"
    echo "----------------------------------------"
    echo ""
    
    echo "DROPLET_HOST: ${DROPLET_HOST:-209.38.62.85}"
    echo "DROPLET_USER: ${DROPLET_USER:-chris}"
    echo ""
    
    # Generate additional secrets
    local mcp_api_key=$(openssl rand -hex 32)
    echo "MCP_API_KEY: $mcp_api_key"
    echo ""
    
    read -p "Have you added all secrets to GitHub? (yes/no): " added
    if [[ "$added" == "yes" ]]; then
        success "GitHub secrets configured"
    else
        warning "Please add secrets to GitHub before running workflows"
    fi
}

# Create directory structure
setup_directories() {
    log "Setting up directory structure..."
    
    local dirs=(
        "$PROJECT_ROOT/logs"
        "$PROJECT_ROOT/deployments"
        "$PROJECT_ROOT/server_config"
        "$PROJECT_ROOT/.github/workflows"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
    done
    
    success "Directory structure created"
}

# Make scripts executable
setup_permissions() {
    log "Setting up file permissions..."
    
    local scripts=(
        "$PROJECT_ROOT/scripts/sync-db-schema.sh"
        "$PROJECT_ROOT/scripts/sync-db-data.sh"
        "$PROJECT_ROOT/scripts/setup-remote-mcp-dev.sh"
        "$PROJECT_ROOT/scripts/setup-ci-cd.sh"
    )
    
    for script in "${scripts[@]}"; do
        if [[ -f "$script" ]]; then
            chmod +x "$script"
        fi
    done
    
    success "File permissions set"
}

# Test deployment workflow
test_deployment() {
    log "Testing deployment workflow..."
    
    # Check if GitHub CLI is available
    if command -v gh &> /dev/null; then
        if gh auth status &> /dev/null; then
            echo "You can test the deployment workflow with:"
            echo "  gh workflow run deploy-mcp.yml"
            success "Ready to test deployment"
        else
            warning "GitHub CLI not authenticated. Install and authenticate gh CLI for easy testing."
        fi
    else
        warning "GitHub CLI not available. You can test workflows through the GitHub web interface."
    fi
}

# Main setup flow
main() {
    echo "========================================"
    echo "ProEthica CI/CD Setup"
    echo "========================================"
    echo ""
    
    # Load environment if available
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        source "$PROJECT_ROOT/.env"
    fi
    
    echo "This script will set up:"
    echo "• SSH keys for deployment"
    echo "• GitHub secrets configuration"
    echo "• Directory structure"
    echo "• File permissions"
    echo "• Deployment testing"
    echo ""
    
    read -p "Continue with setup? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Setup cancelled"
        exit 0
    fi
    
    echo ""
    
    # Run setup steps
    check_prerequisites
    setup_directories
    setup_permissions
    
    echo ""
    echo "Manual setup steps:"
    echo ""
    
    if setup_ssh_keys; then
        echo ""
        setup_github_secrets
    else
        warning "SSH key setup failed. Please set up manually."
    fi
    
    echo ""
    test_deployment
    
    echo ""
    echo "========================================"
    success "CI/CD Setup Complete!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "1. Verify GitHub secrets are configured"
    echo "2. Test deployment workflow"
    echo "3. Set up remote MCP development:"
    echo "   ./scripts/setup-remote-mcp-dev.sh"
    echo "4. Review the CI/CD plan:"
    echo "   cat docs/ci_cd_plan.md"
    echo ""
    echo "Available workflows:"
    echo "• Deploy MCP Server (.github/workflows/deploy-mcp.yml)"
    echo "• Test MCP Server (.github/workflows/test-mcp.yml)"
    echo "• Build Docker Images (.github/workflows/build-mcp-docker.yml)"
    echo "• Monitor Server (.github/workflows/monitor-mcp.yml)"
}

# Run if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi