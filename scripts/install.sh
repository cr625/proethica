#!/bin/bash

# ProEthica Installation Script
# This script sets up ProEthica with PostgreSQL and OntServe integration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 ProEthica Installation Script${NC}"
echo "================================="
echo ""

# Function to print colored messages
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check system requirements
echo "Checking system requirements..."

# Check Python version
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD=python3.12
    print_status "Python 3.12 found"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
    print_status "Python 3.11 found"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD=python3.10
    print_status "Python 3.10 found"
else
    print_error "Python 3.10+ is required"
    echo "Please install Python 3.10 or higher:"
    echo "  Ubuntu/Debian: sudo apt install python3.12 python3.12-venv python3.12-dev"
    echo "  Mac: brew install python@3.12"
    exit 1
fi

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    print_error "PostgreSQL not found"
    echo ""
    echo "Please install PostgreSQL 14+ with pgvector extension:"
    echo ""
    echo "Ubuntu/WSL:"
    echo "  sudo sh -c 'echo \"deb http://apt.postgresql.org/pub/repos/apt \$(lsb_release -cs)-pgdg main\" > /etc/apt/sources.list.d/pgdg.list'"
    echo "  wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -"
    echo "  sudo apt update"
    echo "  sudo apt install -y postgresql-17 postgresql-17-pgvector"
    echo ""
    echo "Mac:"
    echo "  brew install postgresql@17"
    echo "  brew install pgvector"
    echo ""
    exit 1
fi
print_status "PostgreSQL found"

# Check build tools (needed for some Python packages)
if ! command -v gcc &> /dev/null; then
    print_warning "Build tools not found (may be needed for some packages)"
    echo "  Ubuntu/Debian: sudo apt install build-essential libpq-dev"
    echo "  Mac: xcode-select --install"
    echo ""
fi

echo ""
echo "Setting up ProEthica..."
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    print_status "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet
print_status "Pip upgraded"

# Install dependencies
echo "Installing Python dependencies (this may take a few minutes)..."
pip install -r requirements.txt --quiet
print_status "Dependencies installed"

# Database setup
echo ""
echo "Database Configuration"
echo "====================="
echo ""
echo "ProEthica needs a PostgreSQL database. This can be:"
echo "1. The same PostgreSQL instance as OntServe (recommended for development)"
echo "2. A separate PostgreSQL instance"
echo ""

# Get database configuration
read -p "PostgreSQL host [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "PostgreSQL port [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}

read -p "PostgreSQL superuser (for database creation) [postgres]: " DB_SUPERUSER
DB_SUPERUSER=${DB_SUPERUSER:-postgres}

echo "Enter PostgreSQL superuser password (or press Enter if no password):"
read -s DB_SUPERUSER_PASS

# Generate secure password
PROETHICA_DB_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
print_status "Generated secure password for proethica_user"

# Create database and user
echo ""
echo "Creating ProEthica database and user..."

export PGPASSWORD=$DB_SUPERUSER_PASS

# Check if database exists
if psql -h $DB_HOST -p $DB_PORT -U $DB_SUPERUSER -lqt | cut -d \| -f 1 | grep -qw ai_ethical_dm; then
    print_warning "Database 'ai_ethical_dm' already exists"
    read -p "Drop and recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        psql -h $DB_HOST -p $DB_PORT -U $DB_SUPERUSER <<EOF
DROP DATABASE IF EXISTS ai_ethical_dm;
DROP USER IF EXISTS proethica_user;
EOF
    else
        echo "Using existing database..."
        read -p "Enter password for proethica_user: " -s PROETHICA_DB_PASS
        echo
    fi
fi

# Create database and user
psql -h $DB_HOST -p $DB_PORT -U $DB_SUPERUSER <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'proethica_user') THEN
        CREATE USER proethica_user WITH PASSWORD '$PROETHICA_DB_PASS';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE ai_ethical_dm OWNER proethica_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_ethical_dm')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ai_ethical_dm TO proethica_user;
EOF

# Create pgvector extension
psql -h $DB_HOST -p $DB_PORT -U $DB_SUPERUSER -d ai_ethical_dm <<EOF
CREATE EXTENSION IF NOT EXISTS vector;
EOF

unset PGPASSWORD

print_status "Database 'ai_ethical_dm' created with pgvector extension"

# OntServe integration setup
echo ""
echo "OntServe Integration"
echo "==================="
echo ""
echo "ProEthica can integrate with OntServe for ontology management."
echo ""

USE_ONTSERVE="false"
ONTSERVE_URL=""

read -p "Enable OntServe integration? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    USE_ONTSERVE="true"
    
    echo ""
    echo "OntServe integration options:"
    echo "1. Local OntServe instance (http://localhost:8083) - recommended for development"
    echo "2. Remote OntServe instance (custom URL)"
    echo ""
    
    read -p "Choose option (1/2): " -n 1 -r
    echo
    
    if [[ $REPLY == "1" ]]; then
        ONTSERVE_URL="http://localhost:8083"
        print_info "Using local OntServe at $ONTSERVE_URL"
        print_warning "Make sure OntServe is running before starting ProEthica"
    else
        read -p "Enter OntServe URL (e.g., https://api.ontorealm.org): " ONTSERVE_URL
        print_info "Using remote OntServe at $ONTSERVE_URL"
    fi
else
    print_info "OntServe integration disabled (ProEthica will use internal MCP server)"
fi

# API Keys setup
echo ""
echo "API Keys Configuration"
echo "====================="
echo ""
echo "ProEthica supports multiple LLM providers. You can configure these now or later."
echo ""

OPENAI_API_KEY=""
ANTHROPIC_API_KEY=""

read -p "Configure OpenAI API key? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter OpenAI API key: " OPENAI_API_KEY
    print_status "OpenAI API key configured"
fi

read -p "Configure Anthropic (Claude) API key? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter Anthropic API key: " ANTHROPIC_API_KEY
    print_status "Anthropic API key configured"
fi

# Create .env file
echo ""
echo "Creating configuration file..."

cat > .env <<EOF
# ProEthica Configuration
# Generated on $(date)

# Database Configuration
DATABASE_URL=postgresql://proethica_user:${PROETHICA_DB_PASS}@${DB_HOST}:${DB_PORT}/ai_ethical_dm
SQLALCHEMY_DATABASE_URI=postgresql://proethica_user:${PROETHICA_DB_PASS}@${DB_HOST}:${DB_PORT}/ai_ethical_dm

# OntServe Integration
USE_ONTSERVE=${USE_ONTSERVE}
ONTSERVE_URL=${ONTSERVE_URL}
ONTSERVE_WEB_URL=${ONTSERVE_URL/8083/5003}

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=$(openssl rand -hex 32)

# File Storage (Local Filesystem)
UPLOAD_FOLDER=./uploads
MAX_CONTENT_LENGTH=50

# API Keys (add your keys here)
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# Feature Flags
ENHANCED_SCENARIO_GENERATION=true
ENABLE_OBLIGATIONS_EXTRACTION=true
MCP_ONTOLOGY_INTEGRATION=true
USE_DB_VECTOR_SEARCH=true

# Logging
LOG_LEVEL=INFO
DEBUG=false

# Performance
USE_MOCK_GUIDELINE_RESPONSES=false
FORCE_MOCK_LLM=false
EOF

print_status "Configuration file created (.env)"

# Create necessary directories
mkdir -p uploads logs backups
print_status "Created upload, log, and backup directories"

# Initialize database schema
echo ""
echo "Initializing database schema..."

export DATABASE_URL="postgresql://proethica_user:${PROETHICA_DB_PASS}@${DB_HOST}:${DB_PORT}/ai_ethical_dm"
export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"

# Check if we have Flask-Migrate
if [ -f "manage.py" ]; then
    echo "Running database migrations..."
    python manage.py db upgrade
    print_status "Database migrations completed"
elif python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()" 2>/dev/null; then
    print_status "Database schema initialized"
else
    print_warning "Could not initialize database schema automatically"
    echo "Please run the following manually after installation:"
    echo "  python manage.py db upgrade"
    echo "  or"
    echo "  python -c \"from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()\""
fi

# Create start scripts
echo ""
echo "Creating start scripts..."

# Create main start script
cat > start-app.sh <<'EOF'
#!/bin/bash
source venv/bin/activate
export FLASK_ENV=development
export FLASK_APP=app.py

# Check if OntServe integration is enabled
if grep -q "USE_ONTSERVE=true" .env; then
    echo "🔗 OntServe integration enabled"
    ONTSERVE_URL=$(grep ONTSERVE_URL .env | cut -d'=' -f2)
    echo "   URL: $ONTSERVE_URL"
    echo "   Make sure OntServe MCP server is running!"
    echo ""
fi

echo "🚀 Starting ProEthica..."
echo "   Web interface: http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

python run.py
EOF
chmod +x start-app.sh

# Create development script (with debug)
cat > start-dev.sh <<'EOF'
#!/bin/bash
source venv/bin/activate
export FLASK_ENV=development
export FLASK_APP=app.py
export DEBUG=true

echo "🧪 Starting ProEthica in development mode..."
echo "   Web interface: http://localhost:8000"
echo "   Debug mode enabled"
echo ""

python run.py
EOF
chmod +x start-dev.sh

# Create production start script
cat > start-prod.sh <<'EOF'
#!/bin/bash
source venv/bin/activate
export FLASK_ENV=production

echo "🏭 Starting ProEthica in production mode..."
echo "   Using Gunicorn web server"
echo ""

gunicorn -w 2 -b 0.0.0.0:8000 --timeout 120 app:app
EOF
chmod +x start-prod.sh

print_status "Start scripts created"

# Create health check script
cat > health-check.sh <<'EOF'
#!/bin/bash

echo "ProEthica Health Check"
echo "====================="

# Check database connection
source venv/bin/activate
python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

try:
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI')
    if not DATABASE_URL:
        print('❌ No database URL configured')
        exit(1)
    
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute('SELECT version()')
        version = result.fetchone()[0]
        print(f'✅ Database connected: {version.split()[0]} {version.split()[1]}')
        
        # Check pgvector
        result = conn.execute('SELECT * FROM pg_extension WHERE extname = %s', ('vector',))
        if result.fetchone():
            print('✅ pgvector extension available')
        else:
            print('⚠️  pgvector extension not found')
            
except SQLAlchemyError as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
except Exception as e:
    print(f'❌ Health check failed: {e}')
    exit(1)
"

# Check OntServe integration if enabled
if grep -q "USE_ONTSERVE=true" .env; then
    ONTSERVE_URL=$(grep ONTSERVE_URL .env | cut -d'=' -f2)
    echo ""
    echo "Checking OntServe integration..."
    if curl -s "$ONTSERVE_URL/health" > /dev/null 2>&1; then
        echo "✅ OntServe connection successful"
    else
        echo "❌ OntServe connection failed ($ONTSERVE_URL)"
        echo "   Make sure OntServe is running!"
    fi
fi

echo ""
echo "Health check complete!"
EOF
chmod +x health-check.sh

print_status "Health check script created"

# Save credentials
echo ""
echo "Saving credentials..."

cat > credentials.txt <<EOF
ProEthica Installation Credentials
==================================
Generated on: $(date)

Database Connection:
-------------------
Host: $DB_HOST
Port: $DB_PORT
Database: ai_ethical_dm
Username: proethica_user
Password: $PROETHICA_DB_PASS

Connection String:
postgresql://proethica_user:${PROETHICA_DB_PASS}@${DB_HOST}:${DB_PORT}/ai_ethical_dm

OntServe Integration:
--------------------
Enabled: $USE_ONTSERVE
URL: $ONTSERVE_URL

Web Interface:
--------------
Development: http://localhost:8000
Production: Configured via reverse proxy

API Keys:
---------
OpenAI: $([ -n "$OPENAI_API_KEY" ] && echo "Configured" || echo "Not configured")
Anthropic: $([ -n "$ANTHROPIC_API_KEY" ] && echo "Configured" || echo "Not configured")

IMPORTANT: Keep this file secure and do not commit to version control!
EOF

chmod 600 credentials.txt
print_status "Credentials saved to credentials.txt (keep this secure!)"

# Installation complete
echo ""
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo ""
echo "To start ProEthica:"
echo ""
echo "  Development mode:"
echo "    ./start-dev.sh        # With debug enabled"
echo ""
echo "  Production mode:"
echo "    ./start-app.sh        # Standard mode"
echo "    ./start-prod.sh       # With Gunicorn (for production)"
echo ""
echo "  Health check:"
echo "    ./health-check.sh     # Verify installation"
echo ""
echo "Default URL: http://localhost:8000"
echo ""

if [[ $USE_ONTSERVE == "true" ]]; then
    echo -e "${YELLOW}OntServe Integration Enabled:${NC}"
    echo "  Make sure OntServe is running at: $ONTSERVE_URL"
    echo "  Start OntServe first, then start ProEthica"
    echo ""
fi

if [[ -z "$OPENAI_API_KEY" && -z "$ANTHROPIC_API_KEY" ]]; then
    echo -e "${YELLOW}API Keys Notice:${NC}"
    echo "  No LLM API keys configured. Add them to .env file:"
    echo "    OPENAI_API_KEY=your_key_here"
    echo "    ANTHROPIC_API_KEY=your_key_here"
    echo ""
fi

echo "Your credentials are saved in: credentials.txt"
echo "Configuration settings are in: .env"
echo ""
echo "For production deployment, see DEPLOYMENT_PLAN.md"