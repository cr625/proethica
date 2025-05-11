#!/bin/bash
set -e

echo "=== REALM & ProEthica Shared PostgreSQL Setup ==="
echo "Setting up shared PostgreSQL container for both applications..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running or not installed."
  echo "Please start Docker and try again."
  exit 1
fi

# Check if container already exists
if docker ps -a --filter "name=postgres17-pgvector-wsl" --format '{{.Names}}' | grep -q "postgres17-pgvector-wsl"; then
  echo "PostgreSQL container 'postgres17-pgvector-wsl' already exists."
  
  # Check if container is running
  if ! docker ps --filter "name=postgres17-pgvector-wsl" --format '{{.Names}}' | grep -q "postgres17-pgvector-wsl"; then
    echo "Starting existing container..."
    docker start postgres17-pgvector-wsl
  else
    echo "Container is already running."
  fi
else
  echo "Creating new PostgreSQL container..."
  docker run -d --name postgres17-pgvector-wsl \
    -p 5433:5432 \
    -e POSTGRES_PASSWORD=PASS \
    -e POSTGRES_DB=ai_ethical_dm \
    pgvector/pgvector:pg17
  
  echo "Waiting for PostgreSQL to start..."
  sleep 5
fi

# Create the realm database if it doesn't exist
echo "Creating 'realm' database if it doesn't exist..."
if ! docker exec postgres17-pgvector-wsl psql -U postgres -lqt | cut -d \| -f 1 | grep -qw realm; then
  docker exec postgres17-pgvector-wsl psql -U postgres -c "CREATE DATABASE realm;"
  echo "Database 'realm' created successfully."
else
  echo "Database 'realm' already exists."
fi

# Enable pgvector extension on both databases
echo "Enabling pgvector extension on ai_ethical_dm database..."
docker exec postgres17-pgvector-wsl psql -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "Enabling pgvector extension on realm database..."
docker exec postgres17-pgvector-wsl psql -U postgres -d realm -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo ""
echo "=== Setup Complete ==="
echo "PostgreSQL container: postgres17-pgvector-wsl"
echo "Port: 5433"
echo "Username: postgres"
echo "Password: PASS"
echo "Databases:"
echo "  - ai_ethical_dm (for ProEthica)"
echo "  - realm (for REALM application)"
echo ""
echo "Connection URLs:"
echo "  - ProEthica: postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
echo "  - REALM: postgresql://postgres:PASS@localhost:5433/realm"
echo ""
echo "Container status:"
docker ps --filter "name=postgres17-pgvector-wsl" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
