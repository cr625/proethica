# MCP Server Debugging Notes

## Current Issues (2025-01-08)

### 1. Python Import Path Issue
- **Problem**: `ModuleNotFoundError: No module named 'mcp'` when starting server
- **Root Cause**: The `http_ontology_mcp_server.py` imports `mcp.fix_flask_db_config` before setting up sys.path
- **Location**: `/home/chris/proethica-mcp/mcp/http_ontology_mcp_server.py`

### 2. Things to Try on Server

When running Claude on the server, try these fixes:

```bash
# 1. Fix the import order in http_ontology_mcp_server.py
# Move the sys.path.insert BEFORE any mcp imports

# 2. Create a proper startup script
cd /home/chris/proethica-mcp
cat > start_mcp_server.py << 'EOF'
#!/usr/bin/env python3
import os
import sys

# Fix paths FIRST
sys.path.insert(0, '/home/chris/proethica-mcp')
sys.path.insert(0, '/home/chris/proethica-repo')

# Now we can import
from mcp.http_ontology_mcp_server import main

if __name__ == '__main__':
    main()
EOF

# 3. Alternative: Use the enhanced server which seems better structured
python mcp/enhanced_ontology_server_with_guidelines.py

# 4. Check database connection
psql postgresql://postgres:PASS@localhost:5433/ai_ethical_dm -c "SELECT 1"

# 5. Test imports manually
cd /home/chris/proethica-mcp
source mcp-venv/bin/activate
python -c "import sys; sys.path.insert(0, '.'); from mcp.fix_flask_db_config import *"
```

### 3. Environment Setup

The environment needs:
```bash
export PYTHONPATH=/home/chris/proethica-mcp:/home/chris/proethica-repo
export ONTOLOGY_DIR=/home/chris/proethica-repo/ontologies
export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export MCP_SERVER_PORT=5002
export USE_MOCK_GUIDELINE_RESPONSES=true  # Set to false when API key is added
export ANTHROPIC_API_KEY=your-key-here    # Add when available
```

### 4. Quick Debug Commands

```bash
# Check what's running
ps aux | grep -E 'mcp|ontology' | grep -v grep

# Check logs
tail -f /home/chris/proethica-mcp/logs/mcp-*.log

# Test health endpoint
curl http://localhost:5002/health

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Check if app symlink exists
ls -la /home/chris/proethica-mcp/app
```

### 5. Startup Order

1. Source environment variables
2. Activate virtual environment
3. Set PYTHONPATH
4. Start server with proper script

### 6. Alternative Servers Available

- `http_ontology_mcp_server.py` - Main server (has import issues)
- `enhanced_ontology_server_with_guidelines.py` - Enhanced version
- `run_enhanced_mcp_server_with_guidelines.py` - Wrapper script (recommended)

### 7. Next Steps When on Server

1. Fix the import issue in `http_ontology_mcp_server.py`
2. Add ANTHROPIC_API_KEY to mcp.env (or keep mock mode)
3. Create systemd service for automatic startup
4. Configure nginx with the provided ssl config
5. Set up SSL certificate with certbot

### 8. Testing Sequence

```bash
# 1. Start in foreground first
cd /home/chris/proethica-mcp
source mcp.env
source mcp-venv/bin/activate
python mcp/run_enhanced_mcp_server_with_guidelines.py

# 2. If that works, run in background
nohup python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/mcp.log 2>&1 &

# 3. Test health
curl http://localhost:5002/health

# 4. Test from outside (if nginx configured)
curl https://mcp.proethica.org/health
```