#!/bin/bash

# Script to setup environment from GitHub secrets or environment variables
# This can be used in GitHub Codespaces, CI/CD, or local development

echo "Setting up environment configuration..."

# Function to create .env file from environment variables
create_env_from_vars() {
    cat > .env << EOF
# Flask configuration
FLASK_APP=${FLASK_APP:-run.py}
FLASK_ENV=${FLASK_ENV:-development}
SECRET_KEY=${SECRET_KEY:-$(openssl rand -hex 32)}

# Database configuration
DATABASE_URL=${DATABASE_URL:-postgresql://postgres:password@localhost:5433/ai_ethical_dm}

# LLM configuration
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GEMMA_API_KEY=${GEMMA_API_KEY}
USE_CLAUDE=${USE_CLAUDE:-true}
USE_AGENT_ORCHESTRATOR=${USE_AGENT_ORCHESTRATOR:-true}

# Model configuration (new Claude models available: Opus 4 and Sonnet 4)
CLAUDE_DEFAULT_MODEL=${CLAUDE_DEFAULT_MODEL:-claude-sonnet-4-20250514}
CLAUDE_FAST_MODEL=${CLAUDE_FAST_MODEL:-claude-sonnet-4-20250514}
CLAUDE_POWERFUL_MODEL=${CLAUDE_POWERFUL_MODEL:-claude-opus-4-20250514}

# Embedding configuration
EMBEDDING_PROVIDER_PRIORITY=${EMBEDDING_PROVIDER_PRIORITY:-local}
LOCAL_EMBEDDING_MODEL=${LOCAL_EMBEDDING_MODEL:-all-MiniLM-L6-v2}

# Zotero API credentials
ZOTERO_API_KEY=${ZOTERO_API_KEY}
ZOTERO_USER_ID=${ZOTERO_USER_ID}

# Environment and MCP configuration
ENVIRONMENT=${ENVIRONMENT:-development}
MCP_SERVER_URL=${MCP_SERVER_URL:-http://localhost:5001}
MCP_SERVER_PORT=${MCP_SERVER_PORT:-5001}
USE_MOCK_FALLBACK=${USE_MOCK_FALLBACK:-false}
EOF
}

# Function to load from encrypted file
load_from_encrypted() {
    if [ -f ".env.enc" ]; then
        echo "Found encrypted .env file, decrypting..."
        if [ -z "$ENV_DECRYPT_KEY" ]; then
            echo "ERROR: ENV_DECRYPT_KEY not set. Cannot decrypt .env.enc"
            exit 1
        fi
        openssl enc -aes-256-cbc -d -in .env.enc -out .env -k "$ENV_DECRYPT_KEY"
        echo "Environment file decrypted successfully!"
    else
        echo "No encrypted .env file found."
    fi
}

# Function to encrypt .env file
encrypt_env() {
    if [ -f ".env" ]; then
        if [ -z "$1" ]; then
            echo "Usage: $0 encrypt <encryption_key>"
            exit 1
        fi
        openssl enc -aes-256-cbc -salt -in .env -out .env.enc -k "$1"
        echo "Environment file encrypted to .env.enc"
        echo "Add .env.enc to git and share the encryption key securely"
    else
        echo "No .env file found to encrypt"
    fi
}

# Main logic
case "${1:-setup}" in
    "setup")
        if [ -f ".env" ]; then
            echo ".env file already exists. Skipping creation."
        elif [ -f ".env.enc" ]; then
            load_from_encrypted
        else
            create_env_from_vars
            echo "Created .env file from environment variables"
        fi
        ;;
    "encrypt")
        encrypt_env "$2"
        ;;
    "decrypt")
        load_from_encrypted
        ;;
    *)
        echo "Usage: $0 [setup|encrypt|decrypt]"
        exit 1
        ;;
esac

# Verify critical variables
if [ -f ".env" ]; then
    source .env
    echo "Environment configuration complete!"
    echo "Critical variables status:"
    [ -n "$ANTHROPIC_API_KEY" ] && echo "✓ ANTHROPIC_API_KEY is set" || echo "✗ ANTHROPIC_API_KEY is not set"
    [ -n "$DATABASE_URL" ] && echo "✓ DATABASE_URL is set" || echo "✗ DATABASE_URL is not set"
    [ -n "$SECRET_KEY" ] && echo "✓ SECRET_KEY is set" || echo "✗ SECRET_KEY is not set"
fi