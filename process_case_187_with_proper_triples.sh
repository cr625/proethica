#!/bin/bash
# Process Case 187 by removing McLaren extensional triples and adding proper engineering world ontology triples

echo "Making Python script executable..."
chmod +x remove_mclaren_add_proper_triples.py

echo "Removing McLaren triples and adding proper engineering world ontology triples for case 187..."
python remove_mclaren_add_proper_triples.py

echo "Process complete. View case at: http://127.0.0.1:3333/cases/187"
