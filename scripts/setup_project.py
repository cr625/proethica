#!/usr/bin/env python3
"""
ProEthica Project Setup Script

This script helps set up the ProEthica project after cloning by:
1. Creating a Python virtual environment
2. Installing required dependencies
3. Setting up NLTK resources
4. Creating a .env file from template
5. Verifying database connectivity
6. Checking for required services
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(message):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message:^60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}\n")


def print_success(message):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")


def print_warning(message):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.ENDC}")


def print_error(message):
    """Print an error message"""
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")


def print_info(message):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ {message}{Colors.ENDC}")


def check_python_version():
    """Check if Python version is 3.8 or higher"""
    print_header("Checking Python Version")
    
    if sys.version_info < (3, 8):
        print_error(f"Python 3.8 or higher is required. You have Python {sys.version}")
        return False
    
    print_success(f"Python {sys.version.split()[0]} is installed")
    return True


def check_venv():
    """Check if virtual environment exists, create if not"""
    print_header("Setting Up Virtual Environment")
    
    venv_path = Path("venv")
    
    if venv_path.exists():
        print_success("Virtual environment already exists")
        return True
    
    print_info("Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print_success("Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create virtual environment: {e}")
        return False


def get_venv_python():
    """Get the path to Python in the virtual environment"""
    if os.name == 'nt':  # Windows
        return os.path.join("venv", "Scripts", "python.exe")
    else:  # Unix-like
        return os.path.join("venv", "bin", "python")


def install_dependencies():
    """Install required Python packages"""
    print_header("Installing Dependencies")
    
    venv_python = get_venv_python()
    
    # Upgrade pip first
    print_info("Upgrading pip...")
    try:
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True, text=True)
        print_success("pip upgraded successfully")
    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to upgrade pip: {e}")
    
    # Install requirements
    requirements_files = ["requirements.txt", "requirements-mcp.txt"]
    
    for req_file in requirements_files:
        if Path(req_file).exists():
            print_info(f"Installing packages from {req_file}...")
            try:
                result = subprocess.run([venv_python, "-m", "pip", "install", "-r", req_file], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print_success(f"Successfully installed packages from {req_file}")
                else:
                    print_error(f"Some packages failed to install from {req_file}")
                    print(result.stderr)
                    return False
            except Exception as e:
                print_error(f"Failed to install packages from {req_file}: {e}")
                return False
        else:
            print_warning(f"{req_file} not found, skipping...")
    
    return True


def setup_nltk_resources():
    """Download required NLTK resources"""
    print_header("Setting Up NLTK Resources")
    
    venv_python = get_venv_python()
    nltk_script = Path("scripts/setup_nltk_resources.py")
    
    if nltk_script.exists():
        print_info("Downloading NLTK resources...")
        try:
            result = subprocess.run([venv_python, str(nltk_script)], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print_success("NLTK resources downloaded successfully")
                return True
            else:
                print_error("Failed to download NLTK resources")
                print(result.stderr)
                return False
        except Exception as e:
            print_error(f"Failed to run NLTK setup script: {e}")
            return False
    else:
        print_warning("NLTK setup script not found, skipping...")
        return True


def setup_env_file():
    """Create .env file from template if it doesn't exist"""
    print_header("Setting Up Environment Configuration")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print_success(".env file already exists")
        print_info("Please ensure your API keys are configured in .env")
        return True
    
    if env_example.exists():
        print_info("Creating .env file from template...")
        try:
            shutil.copy(env_example, env_file)
            print_success(".env file created from template")
            print_warning("Please edit .env and add your API keys:")
            print("  - ANTHROPIC_API_KEY")
            print("  - OPENAI_API_KEY (optional)")
            return True
        except Exception as e:
            print_error(f"Failed to create .env file: {e}")
            return False
    else:
        print_warning(".env.example not found")
        print_info("Creating basic .env file...")
        try:
            with open(env_file, 'w') as f:
                f.write("""# Flask configuration
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=dev-secret-key-replace-in-production

# Database configuration
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm

# LLM configuration
# IMPORTANT: Add your API keys here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
# OPENAI_API_KEY=your-openai-api-key-here

# Environment and MCP configuration
ENVIRONMENT=development
MCP_SERVER_URL=http://localhost:5001
USE_MOCK_FALLBACK=false
""")
            print_success("Basic .env file created")
            print_warning("Please edit .env and add your API keys")
            return True
        except Exception as e:
            print_error(f"Failed to create .env file: {e}")
            return False


def check_postgresql():
    """Check if PostgreSQL is accessible"""
    print_header("Checking PostgreSQL Connection")
    
    try:
        import psycopg2
        from dotenv import load_dotenv
        
        # Load environment variables
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
        
        # Parse connection string
        if db_url.startswith('postgresql://'):
            db_url = db_url[13:]  # Remove 'postgresql://'
        
        parts = db_url.split('@')
        if len(parts) != 2:
            print_error("Invalid database URL format")
            return False
            
        user_pass = parts[0].split(':')
        host_db = parts[1].split('/')
        
        if len(user_pass) != 2 or len(host_db) != 2:
            print_error("Invalid database URL format")
            return False
            
        user = user_pass[0]
        password = user_pass[1]
        host_port = host_db[0].split(':')
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else '5432'
        database = host_db[1]
        
        print_info(f"Testing connection to {host}:{port}/{database}...")
        
        # Try to connect
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        conn.close()
        
        print_success(f"Successfully connected to PostgreSQL database '{database}'")
        return True
        
    except ImportError:
        print_warning("psycopg2 not installed yet, skipping database check")
        return True
    except Exception as e:
        print_error(f"Failed to connect to PostgreSQL: {e}")
        print_info("Please ensure PostgreSQL is running and accessible")
        print_info("Default connection: postgresql://postgres:PASS@localhost:5433/ai_ethical_dm")
        return False


def check_vscode_settings():
    """Check and update VS Code settings if needed"""
    print_header("Checking VS Code Configuration")
    
    vscode_dir = Path(".vscode")
    launch_json = vscode_dir / "launch.json"
    
    if not launch_json.exists():
        print_warning("No .vscode/launch.json found")
        print_info("VS Code debug configurations will need to be set up manually")
        return True
    
    print_success("VS Code launch.json found")
    print_info("Debug configurations are available")
    return True


def print_next_steps():
    """Print next steps for the user"""
    print_header("Setup Complete - Next Steps")
    
    print("\n1. Edit the .env file and add your API keys:")
    print("   - ANTHROPIC_API_KEY (required for Claude integration)")
    print("   - OPENAI_API_KEY (optional)")
    
    print("\n2. Ensure PostgreSQL is running:")
    print("   - Default port: 5433")
    print("   - Default database: ai_ethical_dm")
    
    print("\n3. Run database migrations:")
    print("   - source venv/bin/activate")
    print("   - flask db upgrade")
    
    print("\n4. Start the application:")
    print("   - Using VS Code: Select 'Flask App - Production MCP' and press F5")
    print("   - Using terminal: source venv/bin/activate && python run_debug_app.py")
    
    print("\n5. Access the application:")
    print("   - Web UI: http://localhost:3333")
    print("   - MCP Server: http://localhost:5001 (if running locally)")


def main():
    """Main setup function"""
    print_header("ProEthica Project Setup")
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Setup virtual environment
    if not check_venv():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies")
        return 1
    
    # Setup NLTK resources
    if not setup_nltk_resources():
        print_warning("NLTK setup failed, but continuing...")
    
    # Setup environment file
    if not setup_env_file():
        print_warning("Environment file setup incomplete")
    
    # Check PostgreSQL
    if not check_postgresql():
        print_warning("PostgreSQL connection failed, but continuing...")
    
    # Check VS Code settings
    check_vscode_settings()
    
    # Print next steps
    print_next_steps()
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}✨ Setup completed successfully!{Colors.ENDC}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())