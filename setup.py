#!/usr/bin/env python3
import os
import subprocess
import sys
import time

def print_header(message):
    """Print a formatted header message."""
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def run_command(command, description=None):
    """Run a shell command and print its output."""
    if description:
        print(f"\n> {description}...")
    
    print(f"$ {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    
    return True

def check_dependencies():
    """Check if required dependencies are installed."""
    print_header("Checking dependencies")
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("Error: Python 3.8 or higher is required")
        return False
    
    # Check if PostgreSQL is installed
    if not run_command("which psql", "Checking PostgreSQL installation"):
        print("PostgreSQL is not installed. Please install PostgreSQL and try again.")
        return False
    
    # Check if UV is installed
    has_uv = run_command("which uv", "Checking UV installation")
    
    return True

def setup_virtual_environment():
    """Set up a virtual environment and install dependencies."""
    print_header("Setting up virtual environment")
    
    # Check if UV is installed
    has_uv = run_command("which uv", "Checking UV installation")
    
    if has_uv:
        # Use UV to create virtual environment and install dependencies
        if not os.path.exists("venv"):
            run_command("uv venv", "Creating virtual environment with UV")
        
        run_command("uv pip install -r requirements.txt", "Installing dependencies with UV")
    else:
        # Use standard Python venv
        if not os.path.exists("venv"):
            run_command("python -m venv venv", "Creating virtual environment")
        
        # Activate virtual environment and install dependencies
        if sys.platform == "win32":
            run_command("venv\\Scripts\\pip install -r requirements.txt", "Installing dependencies")
        else:
            run_command("venv/bin/pip install -r requirements.txt", "Installing dependencies")

def setup_database():
    """Set up the PostgreSQL database."""
    print_header("Setting up database")
    
    db_name = "ai_ethical_dm"
    db_user = "postgres"
    db_password = "postgres"
    
    # Check if database exists
    check_db_cmd = f"psql -U {db_user} -lqt | cut -d \\| -f 1 | grep -qw {db_name}"
    db_exists = subprocess.run(check_db_cmd, shell=True, capture_output=True).returncode == 0
    
    if not db_exists:
        print(f"Creating database '{db_name}'...")
        create_db_cmd = f"createdb -U {db_user} {db_name}"
        if not run_command(create_db_cmd):
            print(f"Error: Failed to create database '{db_name}'")
            return False
    else:
        print(f"Database '{db_name}' already exists")
    
    # Update .env file with database connection
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_content = f.read()
        
        # Update DATABASE_URL if it exists
        if "DATABASE_URL=" in env_content:
            env_content = env_content.replace(
                "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_ethical_dm",
                f"DATABASE_URL=postgresql://{db_user}:{db_password}@localhost:5432/{db_name}"
            )
        
        with open(env_path, "w") as f:
            f.write(env_content)
    
    # Initialize database with Flask-Migrate
    if sys.platform == "win32":
        activate_cmd = "venv\\Scripts\\activate"
        python_cmd = "venv\\Scripts\\python"
    else:
        activate_cmd = "source venv/bin/activate"
        python_cmd = "venv/bin/python"
    
    # Initialize migrations
    run_command(f"{python_cmd} -m flask db init", "Initializing database migrations")
    
    # Create initial migration
    run_command(f"{python_cmd} -m flask db migrate -m 'Initial migration'", "Creating initial migration")
    
    # Apply migration
    run_command(f"{python_cmd} -m flask db upgrade", "Applying migrations")
    
    return True

def main():
    """Main setup function."""
    print_header("AI Ethical Decision-Making Simulator Setup")
    
    # Change to the project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Set up virtual environment
    setup_virtual_environment()
    
    # Set up database
    if not setup_database():
        sys.exit(1)
    
    print_header("Setup complete!")
    print("\nTo run the application:")
    if sys.platform == "win32":
        print("  venv\\Scripts\\python run.py")
    else:
        print("  venv/bin/python run.py")
    
    print("\nOr use Flask's development server:")
    if sys.platform == "win32":
        print("  venv\\Scripts\\flask run")
    else:
        print("  venv/bin/flask run")

if __name__ == "__main__":
    main()
