#!/bin/bash

# ProEthica Production Deployment Script
# Run this script on the production server after SSH'ing in

echo "ProEthica Production Deployment Script"
echo "======================================="
echo ""

# Navigate to ProEthica directory
cd /opt/proethica || exit 1

# Check current status
echo "Current git status:"
git status
echo ""

# Store current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
echo ""

# Fetch latest changes
echo "Fetching latest changes from origin..."
git fetch origin
echo ""

# Pull latest main branch
echo "Pulling latest main branch..."
git pull origin main
echo ""

# Check if there are new database migrations
echo "Checking for database migrations..."
if [ -d "migrations" ]; then
    echo "Migrations directory found. You may need to run database migrations."
    echo "Check with: flask db upgrade"
fi
echo ""

# Check if there are new Python dependencies
echo "Checking for dependency changes..."
if git diff HEAD@{1} HEAD --name-only | grep -q "requirements.txt"; then
    echo "requirements.txt has changed. Installing new dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
else
    echo "No changes to requirements.txt"
fi
echo ""

# Restart ProEthica service
echo "Restarting ProEthica service..."
sudo systemctl restart proethica
echo ""

# Check service status
echo "Checking ProEthica service status..."
sudo systemctl status proethica --no-pager
echo ""

# Check if service is active
if sudo systemctl is-active --quiet proethica; then
    echo "✓ ProEthica service is running"
else
    echo "✗ ProEthica service is not running. Check logs with:"
    echo "  sudo journalctl -u proethica -n 50"
fi
echo ""

# Test the application endpoint
echo "Testing application endpoint..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 | grep -q "200\|302"; then
    echo "✓ Application is responding on port 5000"
else
    echo "✗ Application is not responding properly"
fi
echo ""

echo "Deployment complete!"
echo ""
echo "Access the application at: https://proethica.org"