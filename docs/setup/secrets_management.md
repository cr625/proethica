# Secrets Management Guide

This guide explains how to manage environment variables across different systems without recreating the `.env` file each time you clone the repository.

## Overview

ProEthica uses multiple methods to manage secrets and environment variables:
1. GitHub Secrets (for GitHub Actions and Codespaces)
2. Encrypted environment files
3. Environment-specific configurations
4. Automated setup scripts

## Method 1: GitHub Secrets (Recommended)

### Setting up GitHub Secrets

1. Go to your GitHub repository settings
2. Navigate to Settings → Secrets and variables → Actions
3. Add the following secrets:

```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=<generate-a-secure-random-key>
DATABASE_URL=postgresql://postgres:<your-postgres-password>@localhost:5433/ai_ethical_dm
OPENAI_API_KEY=<your-actual-openai-api-key>
ANTHROPIC_API_KEY=<your-actual-anthropic-api-key>
GEMMA_API_KEY=<your-gemma-api-key-if-using>
USE_CLAUDE=true
USE_AGENT_ORCHESTRATOR=true
CLAUDE_DEFAULT_MODEL=claude-sonnet-4-20250514
CLAUDE_FAST_MODEL=claude-sonnet-4-20250514
CLAUDE_POWERFUL_MODEL=claude-opus-4-20250514
EMBEDDING_PROVIDER_PRIORITY=local
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
ZOTERO_API_KEY=<your-actual-zotero-api-key>
ZOTERO_USER_ID=<your-zotero-user-id>
ENVIRONMENT=development
MCP_SERVER_URL=http://localhost:5001
MCP_SERVER_PORT=5001
USE_MOCK_FALLBACK=false
```

**Important Notes:**
- Replace placeholder values (in angle brackets) with your actual API keys and credentials
- For `SECRET_KEY`, generate a secure random key: `python -c "import secrets; print(secrets.token_hex(32))"`
- The `DATABASE_URL` uses port 5433 (not the default 5432) - adjust based on your PostgreSQL setup
- Never share or commit actual API keys - the placeholders above are just examples

### Using GitHub Secrets

#### In GitHub Codespaces
Secrets are automatically available as environment variables. Run:
```bash
./scripts/setup-env-from-secrets.sh
```

#### In GitHub Actions
The workflow `.github/workflows/setup-env.yml` automatically creates the `.env` file from secrets.

#### Downloading from GitHub Actions
1. Trigger the workflow manually from Actions tab
2. Download the `env-file` artifact
3. Extract the `.env` file to your local repository

## Method 2: Encrypted Environment File

### Creating an Encrypted Environment File

1. Create your `.env` file with all necessary variables
2. Encrypt it:
```bash
./scripts/setup-env-from-secrets.sh encrypt <your-encryption-key>
```
3. This creates `.env.enc` which can be safely committed to the repository
4. Share the encryption key securely with team members

### Using Encrypted Environment File

On a new system:
```bash
export ENV_DECRYPT_KEY=<your-encryption-key>
./scripts/setup-env-from-secrets.sh decrypt
```

## Method 3: Environment Variables

Set environment variables in your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
export ANTHROPIC_API_KEY="your-key"
export DATABASE_URL="postgresql://..."
# ... other variables
```

Then run:
```bash
./scripts/setup-env-from-secrets.sh
```

## Method 4: Automated Setup for Specific Environments

### For Development
```bash
cp .env.example .env
# Edit .env with your values
```

### For Codespaces
The repository automatically uses `config/environments/codespace.py` configuration.

### For WSL
The repository automatically detects WSL and uses `config/environments/wsl.py`.

### For Production
Use the deployment scripts in `mcp/deployment/` with proper production secrets.

## Best Practices

1. **Never commit `.env` files** - They're in `.gitignore` for a reason
2. **Use different secrets for different environments** - Don't share production keys
3. **Rotate secrets regularly** - Especially if they might have been exposed
4. **Use minimal permissions** - API keys should have only necessary permissions
5. **Document required variables** - Keep `.env.example` up to date

## Quick Start for New Developers

1. Clone the repository
2. Choose one method:
   - **GitHub Codespaces**: Just run `./scripts/setup-env-from-secrets.sh`
   - **Local with encryption**: Get the encryption key and run decrypt
   - **Local manual**: Copy `.env.example` to `.env` and fill in values
3. Verify setup: `source .env && echo $ANTHROPIC_API_KEY`

## Troubleshooting

### Missing Variables
The setup script shows which critical variables are missing:
```bash
./scripts/setup-env-from-secrets.sh
# Shows ✓ or ✗ for each critical variable
```

### Permission Errors
Make sure scripts are executable:
```bash
chmod +x scripts/*.sh
```

### Encryption Issues
- Ensure OpenSSL is installed: `sudo apt-get install openssl`
- Use a strong encryption key (min 16 characters)
- Don't lose the encryption key - it can't be recovered

## Security Notes

- GitHub Secrets are encrypted and only exposed to workflows/Codespaces
- Encrypted `.env.enc` files use AES-256-CBC encryption
- Environment variables in shell profiles are visible to all processes
- Consider using a secrets manager (Vault, AWS Secrets Manager) for production