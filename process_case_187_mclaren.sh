#!/bin/bash
# Process Case 187 with McLaren Extensional Definitions
# Uses document entity type for compatibility with case view

echo "Adding McLaren extensional definition triples to case 187..."
python add_mclaren_triples_document.py

echo "Process complete. View case at: http://127.0.0.1:3333/cases/187"
