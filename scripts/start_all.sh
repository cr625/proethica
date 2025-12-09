#!/bin/bash
#
# ProEthica Full Stack Startup Script
# Starts all required services: Redis, OntServe MCP, Celery, Flask
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROETHICA_DIR="$(dirname "$SCRIPT_DIR")"
ONTO_DIR="$(dirname "$PROETHICA_DIR")"
ONTSERVE_DIR="$ONTO_DIR/OntServe"

# Virtual environments
PROETHICA_VENV="$PROETHICA_DIR/venv-proethica"
ONTSERVE_VENV="$ONTSERVE_DIR/venv-ontserve"

# PID files (stored in proethica directory)
PID_DIR="$PROETHICA_DIR/.pids"
mkdir -p "$PID_DIR"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_redis() {
    redis-cli ping > /dev/null 2>&1
    return $?
}

start_redis() {
    log_info "Checking Redis..."
    if check_redis; then
        log_info "Redis is already running"
        return 0
    fi

    log_info "Starting Redis..."
    if command -v systemctl &> /dev/null; then
        sudo systemctl start redis-server 2>/dev/null || sudo service redis-server start 2>/dev/null || redis-server --daemonize yes
    else
        redis-server --daemonize yes
    fi

    # Wait for Redis to start
    for i in {1..10}; do
        if check_redis; then
            log_info "Redis started successfully"
            return 0
        fi
        sleep 1
    done

    log_error "Failed to start Redis"
    return 1
}

check_mcp() {
    nc -z localhost 8082 2>/dev/null
    return $?
}

start_mcp() {
    log_info "Checking OntServe MCP server..."
    if check_mcp; then
        log_info "OntServe MCP server is already running on port 8082"
        return 0
    fi

    if [ ! -f "$ONTSERVE_DIR/servers/mcp_server.py" ]; then
        log_error "OntServe MCP server not found at $ONTSERVE_DIR/servers/mcp_server.py"
        return 1
    fi

    if [ ! -d "$ONTSERVE_VENV" ]; then
        log_error "OntServe venv not found at $ONTSERVE_VENV"
        return 1
    fi

    log_info "Starting OntServe MCP server..."
    cd "$ONTSERVE_DIR"
    source "$ONTSERVE_VENV/bin/activate"
    nohup python servers/mcp_server.py > "$PID_DIR/mcp_server.log" 2>&1 &
    MCP_PID=$!
    echo $MCP_PID > "$PID_DIR/mcp_server.pid"
    deactivate

    # Wait for MCP to start
    for i in {1..15}; do
        if check_mcp; then
            log_info "OntServe MCP server started (PID: $MCP_PID)"
            return 0
        fi
        sleep 1
    done

    log_error "OntServe MCP server failed to start (check $PID_DIR/mcp_server.log)"
    return 1
}

check_celery() {
    pgrep -f "celery.*-A.*celery_config.*worker" > /dev/null 2>&1
    return $?
}

start_celery() {
    log_info "Checking Celery worker..."
    if check_celery; then
        log_info "Celery worker is already running"
        return 0
    fi

    if [ ! -d "$PROETHICA_VENV" ]; then
        log_error "ProEthica venv not found at $PROETHICA_VENV"
        return 1
    fi

    log_info "Starting Celery worker..."
    cd "$PROETHICA_DIR"
    source "$PROETHICA_VENV/bin/activate"
    # IMPORTANT: ProEthica dir must come FIRST so its celery_config.py is found before OntExtract's
    export PYTHONPATH="$PROETHICA_DIR:$ONTO_DIR:$PYTHONPATH"
    nohup celery -A celery_config worker --loglevel=info > "$PID_DIR/celery.log" 2>&1 &
    CELERY_PID=$!
    echo $CELERY_PID > "$PID_DIR/celery.pid"

    # Wait for Celery to initialize
    sleep 3
    if check_celery; then
        log_info "Celery worker started (PID: $CELERY_PID)"
        return 0
    fi

    log_error "Celery worker failed to start (check $PID_DIR/celery.log)"
    return 1
}

start_flask() {
    log_info "Starting ProEthica Flask application..."
    cd "$PROETHICA_DIR"
    source "$PROETHICA_VENV/bin/activate"
    # IMPORTANT: ProEthica dir must come FIRST for correct module resolution
    export PYTHONPATH="$PROETHICA_DIR:$ONTO_DIR:$PYTHONPATH"

    # Run Flask in foreground so user can see output and Ctrl+C to stop
    python run.py
}

show_status() {
    echo ""
    echo "======================================"
    echo "       Service Status Summary         "
    echo "======================================"

    if check_redis; then
        echo -e "  Redis:      ${GREEN}RUNNING${NC}"
    else
        echo -e "  Redis:      ${RED}STOPPED${NC}"
    fi

    if check_mcp; then
        echo -e "  OntServe:   ${GREEN}RUNNING${NC} (port 8082)"
    else
        echo -e "  OntServe:   ${RED}STOPPED${NC}"
    fi

    if check_celery; then
        echo -e "  Celery:     ${GREEN}RUNNING${NC}"
    else
        echo -e "  Celery:     ${RED}STOPPED${NC}"
    fi

    echo "======================================"
    echo ""
}

stop_services() {
    log_info "Stopping services..."

    # Stop Celery
    if [ -f "$PID_DIR/celery.pid" ]; then
        CELERY_PID=$(cat "$PID_DIR/celery.pid")
        if kill -0 $CELERY_PID 2>/dev/null; then
            kill $CELERY_PID 2>/dev/null
            log_info "Stopped Celery (PID: $CELERY_PID)"
        fi
        rm -f "$PID_DIR/celery.pid"
    fi

    # Also kill any other celery workers
    pkill -f "celery.*worker.*celery_config" 2>/dev/null || true

    # Stop MCP server
    if [ -f "$PID_DIR/mcp_server.pid" ]; then
        MCP_PID=$(cat "$PID_DIR/mcp_server.pid")
        if kill -0 $MCP_PID 2>/dev/null; then
            kill $MCP_PID 2>/dev/null
            log_info "Stopped OntServe MCP (PID: $MCP_PID)"
        fi
        rm -f "$PID_DIR/mcp_server.pid"
    fi

    log_info "Services stopped (Redis left running)"
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start   - Start all services and Flask app (default)"
    echo "  stop    - Stop Celery and MCP (leaves Redis running)"
    echo "  status  - Show service status"
    echo "  restart - Stop then start all services"
    echo ""
    echo "Services managed:"
    echo "  - Redis (message broker)"
    echo "  - OntServe MCP server (ontology serving)"
    echo "  - Celery worker (background tasks)"
    echo "  - Flask application (ProEthica web app)"
}

# Main
case "${1:-start}" in
    start)
        echo ""
        echo "======================================"
        echo "    ProEthica Full Stack Startup      "
        echo "======================================"
        echo ""

        start_redis || exit 1
        start_mcp || exit 1
        start_celery || exit 1

        show_status

        log_info "All background services running. Starting Flask..."
        echo ""
        start_flask
        ;;
    stop)
        stop_services
        show_status
        ;;
    status)
        show_status
        ;;
    restart)
        stop_services
        sleep 2
        exec "$0" start
        ;;
    *)
        usage
        exit 1
        ;;
esac
