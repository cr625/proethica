#!/bin/bash
# Add engineering ethics ontology triples to case 187

echo "Making Python script executable..."
chmod +x add_engineering_ethics_triples.py

echo "Adding engineering ethics ontology triples to case 187..."
python add_engineering_ethics_triples.py

echo "Process complete. View case at: http://127.0.0.1:3333/cases/187"
