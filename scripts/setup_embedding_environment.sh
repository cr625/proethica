#!/bin/bash
# Script to set up the embedding environment for the AI Ethical Decision-Making Simulator

# Exit on error
set -e

echo "Setting up embedding environment..."

# Create uploads directory if it doesn't exist
UPLOADS_DIR="app/uploads"
mkdir -p $UPLOADS_DIR
echo "Created uploads directory: $UPLOADS_DIR"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install pgvector extension
echo "Installing pgvector extension..."
./scripts/install_pgvector.sh

# Create database tables
echo "Creating database tables..."
echo "You can create the tables using one of the following methods:"
echo "1. Using Flask-Migrate (recommended):"
echo "   flask db migrate -m \"Add document and document_chunk tables with pgvector support\""
echo "   flask db upgrade"
echo ""
echo "2. Using the manual script:"
echo "   python scripts/manual_create_document_tables.py"
echo ""
echo "Before running these commands, make sure the pgvector extension is enabled in your database:"
echo "   psql -d your_database_name -c \"CREATE EXTENSION IF NOT EXISTS vector;\""

echo ""
echo "Setup completed successfully!"
echo "You can now use the embedding functionality in the AI Ethical Decision-Making Simulator."
