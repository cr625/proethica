#!/bin/bash
#
# ProEthica Codespace Startup Script
# Starts all services without systemd: Redis, OntServe MCP, OntServe Web, Celery, Flask
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Paths
PROETHICA_DIR="/workspaces/proethica"
ONTSERVE_DIR="/workspaces/OntServe"
PROETHICA_VENV="$PROETHICA_DIR/venv-proethica"
ONTSERVE_VENV="$ONTSERVE_DIR/venv-ontserve"
PID_DIR="$PROETHICA_DIR/.pids"
mkdir -p "$PID_DIR"

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------- dependency check ----------

install_deps() {
    local needed=()
    command -v redis-server &>/dev/null || needed+=(redis-server)
    command -v nc &>/dev/null           || needed+=(netcat-openbsd)

    if [ ${#needed[@]} -gt 0 ]; then
        log_info "Installing missing packages: ${needed[*]}"
        sudo apt-get update -qq && sudo apt-get install -yqq "${needed[@]}"
    fi
}

# ---------- postgres ----------

wait_for_postgres() {
    log_info "Waiting for PostgreSQL..."
    for i in {1..30}; do
        if pg_isready -h postgres -q 2>/dev/null; then
            log_info "PostgreSQL is ready"
            return 0
        fi
        sleep 1
    done
    log_error "PostgreSQL not available after 30s"
    return 1
}

# ---------- redis ----------

start_redis() {
    log_info "Checking Redis..."
    if redis-cli ping &>/dev/null; then
        log_info "Redis already running"
        return 0
    fi
    log_info "Starting Redis..."
    redis-server --daemonize yes --loglevel warning
    for i in {1..10}; do
        redis-cli ping &>/dev/null && { log_info "Redis started"; return 0; }
        sleep 1
    done
    log_error "Redis failed to start"; return 1
}

# ---------- OntServe MCP (port 8082) ----------

start_mcp() {
    log_info "Checking OntServe MCP server..."
    if nc -z localhost 8082 2>/dev/null; then
        log_info "OntServe MCP already running on port 8082"
        return 0
    fi
    if [ ! -f "$ONTSERVE_DIR/servers/mcp_server.py" ]; then
        log_error "OntServe MCP not found at $ONTSERVE_DIR/servers/mcp_server.py"; return 1
    fi
    log_info "Starting OntServe MCP server..."
    cd "$ONTSERVE_DIR"
    PYTHONPATH="$ONTSERVE_DIR" nohup "$ONTSERVE_VENV/bin/python" servers/mcp_server.py > "$PID_DIR/mcp_server.log" 2>&1 &
    echo $! > "$PID_DIR/mcp_server.pid"
    for i in {1..15}; do
        nc -z localhost 8082 2>/dev/null && { log_info "OntServe MCP started (PID: $(cat "$PID_DIR/mcp_server.pid"))"; return 0; }
        sleep 1
    done
    log_error "OntServe MCP failed to start — check $PID_DIR/mcp_server.log"; return 1
}

# ---------- OntServe Web (port 5003) ----------

start_ontserve_web() {
    log_info "Checking OntServe Web..."
    if nc -z localhost 5003 2>/dev/null; then
        log_info "OntServe Web already running on port 5003"
        return 0
    fi
    if [ ! -f "$ONTSERVE_DIR/web/app.py" ]; then
        log_warn "OntServe Web not found — skipping"; return 0
    fi
    log_info "Starting OntServe Web..."
    cd "$ONTSERVE_DIR"
    # Run as module-style to keep OntServe root (not web/) as the primary sys.path entry,
    # avoiding web/services/ shadowing the top-level services/ package.
    PYTHONPATH="$ONTSERVE_DIR" nohup "$ONTSERVE_VENV/bin/python" -c "import runpy, sys; sys.path.remove('') if '' in sys.path else None; runpy.run_path('web/app.py', run_name='__main__')" > "$PID_DIR/ontserve_web.log" 2>&1 &
    echo $! > "$PID_DIR/ontserve_web.pid"
    for i in {1..15}; do
        nc -z localhost 5003 2>/dev/null && { log_info "OntServe Web started (PID: $(cat "$PID_DIR/ontserve_web.pid"))"; return 0; }
        # Check if process died (e.g. missing pgvector extension)
        if ! kill -0 "$(cat "$PID_DIR/ontserve_web.pid")" 2>/dev/null; then
            log_warn "OntServe Web failed to start (check $PID_DIR/ontserve_web.log)"
            log_warn "This is non-critical — ProEthica will run without the OntServe Web UI"
            return 0
        fi
        sleep 1
    done
    log_warn "OntServe Web timed out — check $PID_DIR/ontserve_web.log"
    return 0
}

# ---------- celery ----------

start_celery() {
    log_info "Checking Celery worker..."
    if pgrep -f "celery.*-A.*celery_config.*worker" &>/dev/null; then
        log_info "Celery worker already running"
        return 0
    fi
    log_info "Starting Celery worker..."
    cd "$PROETHICA_DIR"
    PYTHONPATH="$PROETHICA_DIR:$(dirname "$PROETHICA_DIR"):$PYTHONPATH" \
        nohup "$PROETHICA_VENV/bin/celery" -A celery_config worker --loglevel=info \
        > "$PID_DIR/celery.log" 2>&1 &
    echo $! > "$PID_DIR/celery.pid"
    sleep 3
    if pgrep -f "celery.*-A.*celery_config.*worker" &>/dev/null; then
        log_info "Celery worker started (PID: $(cat "$PID_DIR/celery.pid"))"
        return 0
    fi
    log_error "Celery failed to start — check $PID_DIR/celery.log"; return 1
}

# ---------- flask ----------

start_flask() {
    log_info "Starting ProEthica Flask app on port 5000..."
    cd "$PROETHICA_DIR"
    source "$PROETHICA_VENV/bin/activate"
    export PYTHONPATH="$PROETHICA_DIR:$(dirname "$PROETHICA_DIR"):$PYTHONPATH"
    # Foreground so you can see output and Ctrl+C to stop
    python run.py
}

# ---------- status ----------

show_status() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}        Service Status Summary          ${NC}"
    echo -e "${CYAN}========================================${NC}"

    redis-cli ping &>/dev/null \
        && echo -e "  Redis:          ${GREEN}RUNNING${NC}  (port 6379)" \
        || echo -e "  Redis:          ${RED}STOPPED${NC}"

    nc -z localhost 8082 2>/dev/null \
        && echo -e "  OntServe MCP:   ${GREEN}RUNNING${NC}  (port 8082)" \
        || echo -e "  OntServe MCP:   ${RED}STOPPED${NC}"

    nc -z localhost 5003 2>/dev/null \
        && echo -e "  OntServe Web:   ${GREEN}RUNNING${NC}  (port 5003)" \
        || echo -e "  OntServe Web:   ${RED}STOPPED${NC}"

    pgrep -f "celery.*worker" &>/dev/null \
        && echo -e "  Celery:         ${GREEN}RUNNING${NC}" \
        || echo -e "  Celery:         ${RED}STOPPED${NC}"

    pg_isready -h postgres -q 2>/dev/null \
        && echo -e "  PostgreSQL:     ${GREEN}RUNNING${NC}  (host: postgres)" \
        || echo -e "  PostgreSQL:     ${RED}STOPPED${NC}"

    echo -e "${CYAN}========================================${NC}"
    echo -e "  Forwarded ports:"
    echo -e "    5000  ProEthica Web"
    echo -e "    5003  OntServe Web"
    echo -e "    8082  OntServe MCP"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# ---------- stop ----------

stop_services() {
    log_info "Stopping services..."

    for svc in celery mcp_server ontserve_web; do
        if [ -f "$PID_DIR/${svc}.pid" ]; then
            pid=$(cat "$PID_DIR/${svc}.pid")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                log_info "Stopped $svc (PID: $pid)"
            fi
            rm -f "$PID_DIR/${svc}.pid"
        fi
    done

    pkill -f "celery.*worker.*celery_config" 2>/dev/null || true
    log_info "Background services stopped (Redis and PostgreSQL left running)"
}

# ---------- logs ----------

show_logs() {
    local svc="${1:-all}"
    case "$svc" in
        mcp)     tail -f "$PID_DIR/mcp_server.log" ;;
        web)     tail -f "$PID_DIR/ontserve_web.log" ;;
        celery)  tail -f "$PID_DIR/celery.log" ;;
        all)     tail -f "$PID_DIR"/*.log ;;
        *)       echo "Usage: $0 logs [mcp|web|celery|all]" ;;
    esac
}

# ---------- main ----------

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start     Start all services + Flask in foreground (default)"
    echo "  stop      Stop background services"
    echo "  restart   Stop then start"
    echo "  status    Show service status"
    echo "  logs      Tail background service logs (mcp|web|celery|all)"
    echo ""
}

case "${1:-start}" in
    start)
        echo ""
        echo -e "${CYAN}======================================${NC}"
        echo -e "${CYAN}  ProEthica Codespace Startup         ${NC}"
        echo -e "${CYAN}======================================${NC}"
        echo ""

        install_deps
        wait_for_postgres || exit 1

        # Ensure NLTK resources are available (Flask won't start without them)
        "$PROETHICA_VENV/bin/python" -c "
import nltk, os
os.makedirs(os.path.expanduser('~/nltk_data'), exist_ok=True)
for pkg in ['punkt', 'punkt_tab', 'stopwords']:
    try:
        nltk.data.find('tokenizers/' + pkg if 'punkt' in pkg else 'corpora/' + pkg)
    except LookupError:
        nltk.download(pkg, quiet=True)
" 2>/dev/null
        start_redis       || exit 1
        start_mcp         || exit 1
        start_ontserve_web || exit 1
        start_celery      || exit 1

        show_status

        log_info "All background services running. Starting Flask..."
        echo ""
        start_flask
        ;;
    stop)
        stop_services
        show_status
        ;;
    restart)
        stop_services
        sleep 2
        exec "$0" start
        ;;
    status)
        install_deps 2>/dev/null
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    *)
        usage
        exit 1
        ;;
esac
