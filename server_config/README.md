# Server Configuration (Legacy)

**⚠️ This directory contains archived/legacy configuration files.**

## Active Deployment Location

The current deployment scripts and documentation have been moved to:
- **MCP Server**: See `/mcp/deployment/` for active deployment scripts
- **Documentation**: See `/mcp/deployment/README_CONSOLIDATED.md` for complete guide

## Archived Files

The `archived/` subdirectory contains outdated service files and scripts from previous deployment strategies:
- Old systemd service files (referenced incorrect paths)
- Gunicorn-based deployment scripts (no longer used)
- Legacy configuration files

These files are kept for historical reference but should not be used for current deployments.

## Migration Note

All active deployment processes have been consolidated in the `/mcp/deployment/` directory. Please refer to that location for:
- Current deployment scripts
- Health check utilities
- Production server configuration
- Deployment documentation

## Dependencies (Historical Reference)

The following Python packages were required for the legacy setup:
- PyPDF2
- python-docx
- beautifulsoup4
- anthropic
- langchain_anthropic