#!/bin/bash
#
# ProEthica Full Stack Restart Script
# Stops all services, then starts them fresh.
# Flask runs in the foreground so output is visible in the console.
# Ctrl+C stops Flask; run stop_all.sh to also stop background services.
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "======================================"
echo "    ProEthica Full Stack Restart      "
echo "======================================"
echo ""

# Stop everything
"$SCRIPT_DIR/stop_all.sh"

echo "Waiting for processes to fully exit..."
sleep 2

# Start everything (Flask runs in foreground)
exec "$SCRIPT_DIR/start_all.sh" start
