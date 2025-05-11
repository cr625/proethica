#!/bin/bash

# Export ontologies from database to TTL files
# This script connects to PostgreSQL and exports ontology content to files

# Database connection parameters
DB_HOST="localhost"
DB_PORT="5433"
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_PASS="PASS"

# Export directory
EXPORT_DIR="${PWD}/ontologies"
mkdir -p $EXPORT_DIR

# Export function
export_ontology() {
  local domain_id=$1
  local output_file="$EXPORT_DIR/$domain_id.ttl"
  
  echo "Exporting ontology '$domain_id' to $output_file..."
  
  # Use psql to fetch the content and write to file
  PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t \
    -c "SELECT content FROM ontologies WHERE domain_id='$domain_id';" > "$output_file"
  
  # Check if export was successful
  if [ -s "$output_file" ]; then
    echo "Successfully exported '$domain_id' ($(wc -c < "$output_file") bytes)"
  else
    echo "Failed to export '$domain_id' or ontology content is empty"
  fi
}

# Export known ontologies
echo "Exporting ontologies to $EXPORT_DIR"
export_ontology "bfo"
export_ontology "proethica-intermediate"
export_ontology "engineering-ethics"

echo "Export completed"
