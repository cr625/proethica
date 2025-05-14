#!/bin/bash

echo "Stopping any running Flask server processes..."
pkill -f "flask run" || echo "No Flask processes found"
pkill -f "python run.py" || echo "No Python run.py processes found"

echo "Restarting the server..."
cd $(dirname $0)
export FLASK_APP=run.py
export FLASK_ENV=development
python run.py
