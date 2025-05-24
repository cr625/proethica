#!/bin/bash
# Run script for the ProEthica experiment interface

echo "Applying SQLAlchemy URL fix patch..."
python patch_sqlalchemy_url.py

echo "Setting environment variables..."
export ENVIRONMENT=codespace
export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export SQLALCHEMY_DATABASE_URI=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export FLASK_DEBUG=1

echo "Starting experiment interface at http://127.0.0.1:5000/experiment/ ..."
python -c "
from app import create_app
app = create_app()
app.run(debug=True, port=5000)
"
