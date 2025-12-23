#!/bin/bash
# Restart Celery worker for ProEthica
#
# Usage: ./scripts/restart_celery.sh [start|stop|status|restart]
#
# Default action is 'restart'

cd /home/chris/onto/proethica

ACTION="${1:-restart}"
LOG_FILE="/tmp/celery_worker.log"

case "$ACTION" in
    stop)
        echo "Stopping Celery worker..."
        pkill -f 'celery.*worker.*celery_config' 2>/dev/null
        sleep 1
        if pgrep -f 'celery.*worker.*celery_config' > /dev/null; then
            echo "Force killing Celery worker..."
            pkill -9 -f 'celery.*worker.*celery_config' 2>/dev/null
        fi
        echo "Celery worker stopped"
        ;;

    start)
        echo "Starting Celery worker..."
        source venv-proethica/bin/activate
        PYTHONPATH=/home/chris/onto:$PYTHONPATH celery -A celery_config.celery worker --loglevel=info --pool=solo > "$LOG_FILE" 2>&1 &
        sleep 3
        if pgrep -f 'celery.*worker.*celery_config' > /dev/null; then
            echo "Celery worker started (PID: $(pgrep -f 'celery.*worker.*celery_config'))"
            echo "Log file: $LOG_FILE"
        else
            echo "Failed to start Celery worker. Check $LOG_FILE for errors."
            tail -20 "$LOG_FILE"
            exit 1
        fi
        ;;

    restart)
        echo "Restarting Celery worker..."
        $0 stop
        $0 start
        ;;

    status)
        if pgrep -f 'celery.*worker.*celery_config' > /dev/null; then
            echo "Celery worker is running (PID: $(pgrep -f 'celery.*worker.*celery_config'))"
            echo ""
            echo "Recent log entries:"
            tail -10 "$LOG_FILE" 2>/dev/null || echo "(no log file)"
        else
            echo "Celery worker is not running"
        fi
        ;;

    *)
        echo "Usage: $0 [start|stop|status|restart]"
        exit 1
        ;;
esac
