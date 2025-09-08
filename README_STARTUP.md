# ProEthica Startup Guide

## Quick Start Options

### 1. Simple Start (Without MCP Server)
```bash
# Start ProEthica without ontology features
cd /home/chris/onto/proethica
export SKIP_MCP=true
python run.py
```

### 2. Start with Manual MCP Server
```bash
# Terminal 1: Start MCP server
cd /home/chris/onto/OntServe
python servers/mcp_server.py

# Terminal 2: Start ProEthica (will detect running MCP)
cd /home/chris/onto/proethica
python run.py
```

### 3. Auto-Start MCP Server
```bash
# ProEthica will automatically start MCP server
cd /home/chris/onto/proethica
export AUTO_START_MCP=true
python run.py
```

### 4. Using the Unified Script
```bash
# Handles everything automatically
cd /home/chris/onto/proethica
./start_services.sh         # Production mode
./start_services.sh --debug  # Development mode
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_MCP` | false | Skip MCP server integration entirely |
| `AUTO_START_MCP` | false | Automatically start MCP server if not running |
| `ONTSERVE_MCP_PORT` | 8082 | Port for MCP server |
| `FLASK_PORT` | 5000 | Port for ProEthica Flask app |
| `DEBUG` | false | Enable Flask debug mode |

## Common Scenarios

### Development Without Ontology Features
```bash
export SKIP_MCP=true
python run.py
```

### Development With Ontology Features
```bash
export AUTO_START_MCP=true
python run.py
```

### Production Deployment
```bash
# Use the startup script
./start_services.sh

# Or with systemd/supervisor managing both services
gunicorn wsgi:application
```

## Troubleshooting

### MCP Server Not Starting
- Check if port 8082 is already in use: `lsof -i :8082`
- Check OntServe database configuration in environment
- Manually start to see errors: `cd ../OntServe && python servers/mcp_server.py`

### ProEthica Runs But No Ontology Features
- This is normal if MCP server isn't running
- Check logs for "MCP server detected" message
- Verify MCP health: `curl http://localhost:8082/health`

### Clean Restart
```bash
# Kill any existing processes
pkill -f "mcp_server.py"
pkill -f "run.py"

# Remove PID file if exists
rm -f /home/chris/onto/proethica/.mcp_server.pid

# Start fresh
export SKIP_MCP=true  # or AUTO_START_MCP=true
python run.py
```

## Notes
- ProEthica works without the MCP server but with limited ontology functionality
- The MCP server provides ontology storage, versioning, and SPARQL query capabilities
- In production, use proper process managers (systemd, supervisor) for both services
