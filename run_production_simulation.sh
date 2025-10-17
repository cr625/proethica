#!/bin/bash
# Start ProEthica in production simulation mode
# This simulates production authentication locally for testing

echo "=========================================="
echo "ProEthica - Production Simulation Mode"
echo "=========================================="
echo ""
echo "Starting server with production authentication enabled..."
echo "Server will run on: http://localhost:5000"
echo ""
echo "Authentication behavior:"
echo "  ✓ LLM operations require login (same as production)"
echo "  ✓ DEBUG mode enabled (helpful errors)"
echo "  ✓ Uses local database (safe testing)"
echo ""
echo "To test:"
echo "  1. Open http://localhost:5000 in private/incognito window"
echo "  2. Click any extraction button"
echo "  3. You should be redirected to login page"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Set environment to production simulation
export FLASK_ENV=production-simulation

# Run the server
python run.py
