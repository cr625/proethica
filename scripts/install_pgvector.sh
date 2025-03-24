#!/bin/bash
# Script to install the pgvector extension for PostgreSQL

# Exit on error
set -e

echo "Installing pgvector extension for PostgreSQL..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Please install PostgreSQL first."
    exit 1
fi

# Get PostgreSQL version
PG_VERSION=$(psql --version | grep -oP 'PostgreSQL \K[0-9]+\.[0-9]+')
echo "Detected PostgreSQL version: $PG_VERSION"

# Check if we're on Ubuntu/Debian or RHEL/CentOS
if [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu system"
    
    # Install build dependencies
    echo "Installing build dependencies..."
    sudo apt-get update
    sudo apt-get install -y postgresql-server-dev-$PG_VERSION build-essential git
    
    # Clone pgvector repository
    echo "Cloning pgvector repository..."
    git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git /tmp/pgvector
    
    # Build and install pgvector
    echo "Building and installing pgvector..."
    cd /tmp/pgvector
    make
    sudo make install
    
    # Clean up
    cd -
    rm -rf /tmp/pgvector
    
elif [ -f /etc/redhat-release ]; then
    echo "Detected RHEL/CentOS system"
    
    # Install build dependencies
    echo "Installing build dependencies..."
    sudo yum install -y postgresql-devel gcc git
    
    # Clone pgvector repository
    echo "Cloning pgvector repository..."
    git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git /tmp/pgvector
    
    # Build and install pgvector
    echo "Building and installing pgvector..."
    cd /tmp/pgvector
    make
    sudo make install
    
    # Clean up
    cd -
    rm -rf /tmp/pgvector
    
elif [ "$(uname)" == "Darwin" ]; then
    echo "Detected macOS system"
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew is not installed. Please install Homebrew first."
        exit 1
    fi
    
    # Install pgvector using Homebrew
    echo "Installing pgvector using Homebrew..."
    brew install pgvector
    
else
    echo "Unsupported operating system. Please install pgvector manually."
    echo "Visit https://github.com/pgvector/pgvector for installation instructions."
    exit 1
fi

echo ""
echo "pgvector extension installed successfully!"
echo ""
echo "To enable the extension in your database, run:"
echo "psql -d your_database_name -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
echo ""
echo "You can also use the provided script:"
echo "./scripts/enable_pgvector.sql"
