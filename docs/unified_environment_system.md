# Unified Environment System

This document explains the implementation of the unified environment detection and configuration system that allows running the application across different environments (development, WSL, GitHub Codespaces, production) without requiring separate branches.

## Overview

The unified environment system automatically detects the current environment and loads the appropriate configuration settings. This approach eliminates the need for separate environment-specific branches (like `codespace-environment` and `agent-ontology-dev`), simplifying branch management and reducing merge conflicts.

## How It Works

### 1. Environment Detection

The system detects the current environment using the following priority order:

1. Checks for GitHub Codespaces environment (`CODESPACES` environment variable)
2. Checks for WSL environment (by examining `/proc/version`)
3. Uses the explicitly set `ENVIRONMENT` variable if available
4. Falls back to hostname or git branch detection

Implementation is in `config/environment.py`:

```python
# Environment detection
# Check if we're in GitHub Codespaces
if os.environ.get('CODESPACES', '').lower() == 'true':
    ENVIRONMENT = 'codespace'
    logger.info("Detected GitHub Codespaces environment")
# Check if we're in WSL
elif sys.platform == 'linux' and os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower():
    ENVIRONMENT = 'wsl'
    logger.info("Detected WSL environment")
else:
    # Default to environment variable if set, otherwise development
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development').lower()
    logger.info(f"Using environment from configuration: {ENVIRONMENT}")
```

### 2. Environment-Specific Configuration

Each environment has its own configuration file:

- `config/environments/development.py` - Standard development environment
- `config/environments/wsl.py` - Windows Subsystem for Linux settings
- `config/environments/codespace.py` - GitHub Codespaces settings
- `config/environments/production.py` - Production environment settings

The system dynamically loads the appropriate configuration:

```python
try:
    config_module = importlib.import_module(f"config.environments.{ENVIRONMENT}")
    # Export all settings from the environment module
    for setting in dir(config_module):
        if not setting.startswith('_'):  # Skip private attributes
            globals()[setting] = getattr(config_module, setting)
except ImportError as e:
    logger.error(f"Failed to load configuration for {ENVIRONMENT}: {str(e)}")
```

### 3. Startup Scripts

The startup scripts (`auto_run.sh` and `start_proethica.sh`) have been enhanced to:

1. Auto-detect the environment
2. Apply environment-specific setup steps (like database configuration)
3. Start the appropriate services with the correct settings

## Environment-Specific Features

### WSL Environment

- Sets the appropriate Chrome executable path for Puppeteer
- Manages PostgreSQL service automatically
- Creates required directories with the correct paths

### GitHub Codespaces

- Uses Docker for PostgreSQL (port 5433)
- Configures paths appropriate for Codespaces workspace
- Runs specialized setup script for database preparation

### Development

- Standard development settings
- Works on regular Linux/macOS environments

### Production

- Optimized for production deployment
- Secure settings and appropriate logging levels

## Benefits

1. **Simplified Git Workflow**: One development branch for all environments
2. **Reduced Merge Conflicts**: No need to sync changes between environment branches
3. **Cleaner Version History**: Git history follows feature development, not environment tweaks
4. **Improved Developer Experience**: Auto-detection means no manual configuration needed
5. **Consistent Environment Handling**: Standard approach across all environments

## Implementation Notes

- The configuration system ensures appropriate fallbacks if specific environment files are missing
- Directory paths are automatically created if they don't exist
- Comprehensive logging helps diagnose configuration issues
