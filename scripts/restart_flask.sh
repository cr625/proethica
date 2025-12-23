#!/bin/bash
# Restart Flask server for ProEthica
#
# Usage: ./scripts/restart_flask.sh [start|stop|status|restart]
#
# Default action is 'restart'

cd /home/chris/onto/proethica

ACTION="${1:-restart}"
LOG_FILE="/tmp/flask.log"
PID_FILE="/tmp/flask.pid"

case "$ACTION" in
    stop)
        echo "Stopping Flask server..."
        pkill -f 'python run.py' 2>/dev/null
        sleep 1
        if pgrep -f 'python run.py' > /dev/null; then
            echo "Force killing Flask server..."
            pkill -9 -f 'python run.py' 2>/dev/null
        fi
        rm -f "$PID_FILE"
        echo "Flask server stopped"
        ;;

    start)
        echo "Starting Flask server..."
        source venv-proethica/bin/activate
        nohup python run.py > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        sleep 3
        if curl -s http://localhost:5000/ > /dev/null 2>&1; then
            echo "Flask server started (PID: $(cat $PID_FILE))"
            echo "Log file: $LOG_FILE"
            echo "URL: http://localhost:5000"
        else
            echo "Flask server may still be starting. Check $LOG_FILE for status."
            tail -10 "$LOG_FILE"
        fi
        ;;

    restart)
        echo "Restarting Flask server..."
        $0 stop
        $0 start
        ;;

    status)
        if pgrep -f 'python run.py' > /dev/null; then
            echo "Flask server is running (PID: $(pgrep -f 'python run.py'))"
            echo ""
            echo "Recent log entries:"
            tail -10 "$LOG_FILE" 2>/dev/null || echo "(no log file)"
        else
            echo "Flask server is not running"
        fi
        ;;

    *)
        echo "Usage: $0 [start|stop|status|restart]"
        exit 1
        ;;
esac
