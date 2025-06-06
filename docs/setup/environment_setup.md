# Environment Setup Guide

This document explains how to configure and run the application in different environments (development and production).

## Quick Setup

For a quick and automated setup of the development environment, run:

```bash
python setup_project.py
```

This script will:
- Check Python version (3.8+ required)
- Create a virtual environment
- Install all dependencies
- Download NLTK resources
- Create .env file from template
- Check PostgreSQL connectivity
- Provide clear next steps

For manual setup or production environments, continue reading below.

## Environment Configuration System

The application now uses an environment-aware configuration system that automatically detects whether it's running in development or production and applies the appropriate settings. This enables a seamless transition between environments without manual changes.

### Directory Structure

```
config/
  ├── __init__.py
  ├── environment.py                   # Main environment detector and loader
  └── environments/
      ├── __init__.py 
      ├── development.py               # Development environment settings
      └── production.py                # Production environment settings
```

### How It Works

1. The `environment.py` module detects the current environment based on:
   - The `ENVIRONMENT` environment variable
   - Or defaults to 'development' if not specified

2. Environment-specific settings are loaded from the appropriate file
   - `config/environments/development.py` for development
   - `config/environments/production.py` for production

3. The settings are exposed as module-level variables that can be imported by other modules:
   ```python
   from config.environment import DB_PORT, MCP_SERVER_PORT, LOG_DIR
   ```

## Key Environment Differences

| Setting | Development | Production |
|---------|------------|------------|
| DB_PORT | 5432 | 5433 |
| LOCK_FILE_PATH | ./tmp/enhanced_mcp_server.lock | /tmp/enhanced_mcp_server.lock |
| LOG_DIR | ./logs | /var/log/proethica |
| DEBUG | True | False |
| VERBOSE_LOGGING | True | False |

## MCP Server Management

The MCP server management has been enhanced to be environment-aware:

### Scripts

- `scripts/restart_mcp_server.sh`: Bash wrapper that detects the environment and calls the Python script
- `scripts/env_mcp_server.py`: Python script that loads environment-specific configuration and manages the MCP server

### Usage

To start the MCP server in development mode (default):

```bash
./scripts/restart_mcp_server.sh
```

To start the MCP server in production mode:

```bash
ENVIRONMENT=production ./scripts/restart_mcp_server.sh
```

You can also set the ENVIRONMENT in your `.env` file:

```
ENVIRONMENT=production
```

## Setting Up a New Environment

### Development Environment Setup

1. Ensure you're on the `agent-ontology-dev` branch:
   ```bash
   git checkout agent-ontology-dev
   ```

2. Create required local directories:
   ```bash
   mkdir -p logs tmp
   ```

3. Start the MCP server with development settings:
   ```bash
   ./scripts/restart_mcp_server.sh
   ```

### Production Environment Setup

1. Switch to the `agent-ontology-integration` branch:
   ```bash
   git checkout agent-ontology-integration
   ```

2. Set the environment variable:
   ```bash
   echo "ENVIRONMENT=production" >> .env
   ```

3. Ensure the log directory exists:
   ```bash
   sudo mkdir -p /var/log/proethica
   sudo chown $USER:$USER /var/log/proethica
   ```

4. Start the MCP server with production settings:
   ```bash
   ./scripts/restart_mcp_server.sh
   ```

## Troubleshooting

### Common Issues

1. **Port conflicts**:
   - Check if another process is using the port:
     ```bash
     lsof -i:5001
     ```
   - Stop the process manually:
     ```bash
     kill -9 <PID>
     ```

2. **Incorrect environment detection**:
   - Verify your current environment:
     ```bash
     grep ENVIRONMENT .env || echo "Not set in .env file"
     echo $ENVIRONMENT
     ```
   - Explicitly set the environment if needed:
     ```bash
     export ENVIRONMENT=development  # or production
     ```

3. **Permission issues with log directory**:
   - For production:
     ```bash
     sudo chown -R $USER:$USER /var/log/proethica
     ```
   - For development, ensure the local logs directory exists:
     ```bash
     mkdir -p logs
     ```

## Best Practices

1. **Environment Variable Management**:
   - Always set the `ENVIRONMENT` variable in your `.env` file to ensure consistency
   - For CI/CD pipelines, set the environment variable in your deployment configuration

2. **Branch Management**:
   - Use `agent-ontology-dev` branch for development
   - Use `agent-ontology-integration` branch for production
   - Keep the branches in sync by periodically merging the dev branch into the production branch

3. **Testing across environments**:
   - Test changes in development first before applying to production
   - Use environment-specific configuration for testing
   - Script your tests to run in both environments for comparison

4. **Adding New Settings**:
   - When adding new environment-specific settings, add them to both environment files
   - Document the differences in this guide
   - Provide appropriate default values in the main environment loader

## How Environment Configuration Affects MCP Server

The MCP server now uses the following environment-specific settings:

1. **Port Configuration**:
   - The port remains 5001 for both development and production
   - Database port differs (5432 for development, 5433 for production)

2. **Lock File Location**:
   - Development: Uses local directory `./tmp/enhanced_mcp_server.lock`
   - Production: Uses system directory `/tmp/enhanced_mcp_server.lock`

3. **Logging**:
   - Development: Logs to `./logs/enhanced_mcp_server.log` with verbose output
   - Production: Logs to `/var/log/proethica/enhanced_mcp_server.log` with minimal output

4. **Error Handling**:
   - Development: More detailed error messages and debug information
   - Production: Concise error messages focused on recovery steps

## Deployment Pipeline

To implement a robust deployment pipeline that keeps both environments in sync:

1. **Development Flow**:
   ```
   Local Development → Testing → Commit to agent-ontology-dev branch
   ```

2. **Production Deployment**:
   ```
   Review Changes → Merge to agent-ontology-integration → Deploy to Server
   ```

3. **Emergency Fixes**:
   - Fix can be applied directly to production branch
   - Always backport fixes to development branch afterward

4. **Environment Identification**:
   - Each environment should be clearly labeled in UI (e.g., dev/prod indicator)
   - Log messages should include environment information
   - Automated tests should verify correct environment settings

## Conclusion

By using this environment-aware configuration system, we can maintain a clean separation between development and production environments while sharing the same codebase. This approach makes it easier to develop and test locally without worrying about production-specific settings, and ensures that production deployments use the appropriate configuration for reliability and security.
