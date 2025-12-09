#!/bin/bash
#
# ProEthica Full Stack Startup with Logging
# Starts all services and logs everything to timestamped files
#
# Usage:
#   ./scripts/start_with_logging.sh          # Start all with logging, Flask in foreground
#   ./scripts/start_with_logging.sh bg       # Start all in background, tail logs
#   ./scripts/start_with_logging.sh tail     # Just tail existing logs
#   ./scripts/start_with_logging.sh stop     # Stop all services
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROETHICA_DIR="$(dirname "$SCRIPT_DIR")"
ONTO_DIR="$(dirname "$PROETHICA_DIR")"
ONTSERVE_DIR="$ONTO_DIR/OntServe"

# Virtual environments
PROETHICA_VENV="$PROETHICA_DIR/venv-proethica"
ONTSERVE_VENV="$ONTSERVE_DIR/venv-ontserve"

# Log directory with timestamp
LOG_DIR="$PROETHICA_DIR/logs"
mkdir -p "$LOG_DIR"

# Current session logs (symlinks to latest)
MCP_LOG="$LOG_DIR/mcp_server.log"
CELERY_LOG="$LOG_DIR/celery.log"
FLASK_LOG="$LOG_DIR/flask.log"
COMBINED_LOG="$LOG_DIR/combined.log"

# PID files
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

log_header() {
    echo -e "${CYAN}$1${NC}"
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

    log_info "Starting OntServe MCP server (logging to $MCP_LOG)..."

    # Clear old log
    > "$MCP_LOG"

    cd "$ONTSERVE_DIR"
    source "$ONTSERVE_VENV/bin/activate"
    nohup python servers/mcp_server.py >> "$MCP_LOG" 2>&1 &
    MCP_PID=$!
    echo $MCP_PID > "$PID_DIR/mcp_server.pid"
    deactivate

    for i in {1..15}; do
        if check_mcp; then
            log_info "OntServe MCP server started (PID: $MCP_PID)"
            return 0
        fi
        sleep 1
    done

    log_error "OntServe MCP server failed to start (check $MCP_LOG)"
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

    log_info "Starting Celery worker (logging to $CELERY_LOG)..."

    # Clear old log
    > "$CELERY_LOG"

    cd "$PROETHICA_DIR"
    source "$PROETHICA_VENV/bin/activate"
    export PYTHONPATH="$PROETHICA_DIR:$ONTO_DIR:$PYTHONPATH"
    nohup celery -A celery_config worker --loglevel=info >> "$CELERY_LOG" 2>&1 &
    CELERY_PID=$!
    echo $CELERY_PID > "$PID_DIR/celery.pid"

    sleep 3
    if check_celery; then
        log_info "Celery worker started (PID: $CELERY_PID)"
        return 0
    fi

    log_error "Celery worker failed to start (check $CELERY_LOG)"
    return 1
}

check_flask() {
    nc -z localhost 5000 2>/dev/null
    return $?
}

start_flask_foreground() {
    log_info "Starting ProEthica Flask (logging to $FLASK_LOG + console)..."

    # Clear old log
    > "$FLASK_LOG"

    cd "$PROETHICA_DIR"
    source "$PROETHICA_VENV/bin/activate"
    export PYTHONPATH="$PROETHICA_DIR:$ONTO_DIR:$PYTHONPATH"

    # Run Flask with tee to capture to file AND show on console
    python run.py 2>&1 | tee -a "$FLASK_LOG"
}

start_flask_background() {
    log_info "Starting ProEthica Flask in background (logging to $FLASK_LOG)..."

    if check_flask; then
        log_info "Flask is already running on port 5000"
        return 0
    fi

    # Clear old log
    > "$FLASK_LOG"

    cd "$PROETHICA_DIR"
    source "$PROETHICA_VENV/bin/activate"
    export PYTHONPATH="$PROETHICA_DIR:$ONTO_DIR:$PYTHONPATH"

    nohup python run.py >> "$FLASK_LOG" 2>&1 &
    FLASK_PID=$!
    echo $FLASK_PID > "$PID_DIR/flask.pid"

    for i in {1..15}; do
        if check_flask; then
            log_info "Flask started (PID: $FLASK_PID)"
            return 0
        fi
        sleep 1
    done

    log_error "Flask failed to start (check $FLASK_LOG)"
    return 1
}

tail_logs() {
    log_header "
============================================
       Tailing All Service Logs
============================================
  MCP:    $MCP_LOG
  Celery: $CELERY_LOG
  Flask:  $FLASK_LOG
============================================
Press Ctrl+C to stop tailing (services keep running)
"
    # Use tail -F to follow logs even if they're recreated
    tail -F "$MCP_LOG" "$CELERY_LOG" "$FLASK_LOG" 2>/dev/null
}

show_status() {
    echo ""
    log_header "======================================"
    log_header "       Service Status Summary         "
    log_header "======================================"

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

    if check_flask; then
        echo -e "  Flask:      ${GREEN}RUNNING${NC} (port 5000)"
    else
        echo -e "  Flask:      ${RED}STOPPED${NC}"
    fi

    log_header "======================================"
    echo ""
    log_header "Log files:"
    echo "  MCP:    $MCP_LOG"
    echo "  Celery: $CELERY_LOG"
    echo "  Flask:  $FLASK_LOG"
    echo ""
}

stop_services() {
    log_info "Stopping services..."

    # Stop Flask
    if [ -f "$PID_DIR/flask.pid" ]; then
        FLASK_PID=$(cat "$PID_DIR/flask.pid")
        if kill -0 $FLASK_PID 2>/dev/null; then
            kill $FLASK_PID 2>/dev/null
            log_info "Stopped Flask (PID: $FLASK_PID)"
        fi
        rm -f "$PID_DIR/flask.pid"
    fi
    pkill -f "python.*run.py" 2>/dev/null || true

    # Stop Celery
    if [ -f "$PID_DIR/celery.pid" ]; then
        CELERY_PID=$(cat "$PID_DIR/celery.pid")
        if kill -0 $CELERY_PID 2>/dev/null; then
            kill $CELERY_PID 2>/dev/null
            log_info "Stopped Celery (PID: $CELERY_PID)"
        fi
        rm -f "$PID_DIR/celery.pid"
    fi
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
    echo "  (none)  - Start all services, Flask in foreground with logging"
    echo "  bg      - Start all services in background, then tail logs"
    echo "  tail    - Just tail existing log files"
    echo "  stop    - Stop all services (except Redis)"
    echo "  status  - Show service status and log locations"
    echo ""
    echo "Log files are stored in: $LOG_DIR/"
    echo ""
    echo "To monitor logs from another terminal:"
    echo "  tail -f $LOG_DIR/flask.log"
    echo "  tail -f $LOG_DIR/celery.log"
    echo "  tail -f $LOG_DIR/mcp_server.log"
}

# Main
case "${1:-}" in
    ""|fg|foreground)
        log_header "
============================================
   ProEthica Full Stack Startup (Logging)
============================================
"
        start_redis || exit 1
        start_mcp || exit 1
        start_celery || exit 1

        show_status

        log_info "All background services running. Starting Flask with logging..."
        echo ""
        start_flask_foreground
        ;;
    bg|background)
        log_header "
============================================
   ProEthica Background Mode (All Logged)
============================================
"
        start_redis || exit 1
        start_mcp || exit 1
        start_celery || exit 1
        start_flask_background || exit 1

        show_status

        log_info "All services running in background. Tailing logs..."
        sleep 2
        tail_logs
        ;;
    tail)
        tail_logs
        ;;
    stop)
        stop_services
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        usage
        exit 1
        ;;
esac
