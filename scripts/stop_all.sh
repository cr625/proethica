#!/bin/bash
#
# ProEthica Full Stack Stop Script
# Stops all services: Flask, Celery, OntServe MCP
# Leaves Redis running (shared system service)
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROETHICA_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROETHICA_DIR/.pids"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "======================================"
echo "     ProEthica Full Stack Stop        "
echo "======================================"
echo ""

# Stop Flask (python run.py)
FLASK_PIDS=$(pgrep -f "python.*run\.py" 2>/dev/null || true)
if [ -n "$FLASK_PIDS" ]; then
    echo "$FLASK_PIDS" | xargs kill 2>/dev/null || true
    log_info "Stopped Flask (PIDs: $(echo $FLASK_PIDS | tr '\n' ' '))"
else
    log_info "Flask not running"
fi

# Stop Celery via PID file
if [ -f "$PID_DIR/celery.pid" ]; then
    CELERY_PID=$(cat "$PID_DIR/celery.pid")
    if kill -0 "$CELERY_PID" 2>/dev/null; then
        kill "$CELERY_PID" 2>/dev/null
        log_info "Stopped Celery (PID: $CELERY_PID)"
    fi
    rm -f "$PID_DIR/celery.pid"
fi
# Also kill any stray celery workers
pkill -f "celery.*worker.*celery_config" 2>/dev/null && log_info "Stopped stray Celery workers" || true

# Stop OntServe MCP via PID file
if [ -f "$PID_DIR/mcp_server.pid" ]; then
    MCP_PID=$(cat "$PID_DIR/mcp_server.pid")
    if kill -0 "$MCP_PID" 2>/dev/null; then
        kill "$MCP_PID" 2>/dev/null
        log_info "Stopped OntServe MCP (PID: $MCP_PID)"
    fi
    rm -f "$PID_DIR/mcp_server.pid"
fi
# Also kill any stray MCP server processes
pkill -f "python.*mcp_server\.py" 2>/dev/null && log_info "Stopped stray MCP processes" || true

# Brief wait for processes to exit
sleep 1

# Status check
echo ""
echo "======================================"
echo "       Service Status Summary         "
echo "======================================"

if redis-cli ping > /dev/null 2>&1; then
    echo -e "  Redis:      ${GREEN}RUNNING${NC} (left running)"
else
    echo -e "  Redis:      ${RED}STOPPED${NC}"
fi

if nc -z localhost 8082 2>/dev/null; then
    echo -e "  OntServe:   ${YELLOW}STILL RUNNING${NC} (port 8082)"
else
    echo -e "  OntServe:   ${RED}STOPPED${NC}"
fi

if pgrep -f "celery.*worker.*celery_config" > /dev/null 2>&1; then
    echo -e "  Celery:     ${YELLOW}STILL RUNNING${NC}"
else
    echo -e "  Celery:     ${RED}STOPPED${NC}"
fi

if pgrep -f "python.*run\.py" > /dev/null 2>&1; then
    echo -e "  Flask:      ${YELLOW}STILL RUNNING${NC}"
else
    echo -e "  Flask:      ${RED}STOPPED${NC}"
fi

echo "======================================"
echo ""
