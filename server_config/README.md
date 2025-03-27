# Server-Specific Configuration

This directory contains configuration files specific to this server deployment. These files are not tracked by git to avoid conflicts when syncing with local development environments.

## Files

- `proethica.service`: Systemd service file for running the application with gunicorn
- `run_with_agents_gunicorn.sh`: Script to run the application with gunicorn and the agent orchestrator enabled
- `restart_mcp_server_gunicorn.sh`: Modified script to restart the MCP server with server-specific paths

## Installation

To install the service:

1. Copy the service file to the systemd directory:
   ```
   sudo cp server_config/proethica.service /etc/systemd/system/
   ```

2. Reload systemd:
   ```
   sudo systemctl daemon-reload
   ```

3. Enable and start the service:
   ```
   sudo systemctl enable proethica
   sudo systemctl start proethica
   ```

## Dependencies

The following Python packages are required:
- PyPDF2
- python-docx
- beautifulsoup4
- anthropic
- langchain_anthropic
