#!/usr/bin/env python
"""
ProEthica Flask Application Entry Point
"""

import os
import sys
import logging
import subprocess
import socket
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Add the shared directory to Python path (for llm_orchestration imports)
shared_dir = project_root.parent / "shared"
if shared_dir.exists():
    sys.path.insert(0, str(shared_dir.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def check_mcp_server(host='localhost', port=8082):
    """Check if OntServe MCP server is running."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def check_redis(host='localhost', port=6379, db=1):
    """Check if Redis is running and accessible."""
    try:
        import redis
        r = redis.Redis(host=host, port=port, db=db, socket_timeout=2)
        r.ping()
        info = r.info('server')
        return True, info.get('redis_version', 'unknown')
    except ImportError:
        return False, "redis library not installed"
    except Exception as e:
        return False, str(e)


def check_celery_worker():
    """Check if Celery worker is running."""
    try:
        # Check for celery process
        result = subprocess.run(
            ['pgrep', '-f', 'celery.*worker'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def check_pipeline_services():
    """Check all pipeline-related services and log their status."""
    logger.info("=" * 50)
    logger.info("Pipeline Service Status Check")
    logger.info("=" * 50)

    # Check Redis
    redis_ok, redis_info = check_redis()
    if redis_ok:
        logger.info(f"  Redis: Connected (v{redis_info})")
    else:
        logger.warning(f"  Redis: NOT CONNECTED - {redis_info}")
        logger.warning("    Pipeline automation will not work without Redis!")
        logger.warning("    Start Redis with: sudo service redis-server start")

    # Check Celery (warning only - it might start later)
    celery_ok = check_celery_worker()
    if celery_ok:
        logger.info("  Celery: Worker running")
    else:
        logger.info("  Celery: No worker detected (start separately if needed)")
        logger.info("    Start Celery with: celery -A celery_config worker --loglevel=info")

    logger.info("=" * 50)

    return redis_ok

def start_mcp_server():
    """Attempt to start the OntServe MCP server."""
    try:
        # Path to MCP server
        mcp_server_path = project_root.parent / "OntServe" / "servers" / "mcp_server.py"
        
        if not mcp_server_path.exists():
            logger.warning(f"MCP server script not found at {mcp_server_path}")
            return False
        
        # Check if process is already running (zombie process)
        pid_file = project_root / ".mcp_server.pid"
        if pid_file.exists():
            try:
                with open(pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                # Check if old process is still running
                os.kill(old_pid, 0)
                logger.info(f"MCP server already running with PID {old_pid}")
                return check_mcp_server()
            except (OSError, ValueError):
                # Process doesn't exist, remove stale PID file
                pid_file.unlink(missing_ok=True)
        
        # Start MCP server in background
        logger.info("Starting OntServe MCP server...")
        process = subprocess.Popen(
            [sys.executable, str(mcp_server_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Save PID for later cleanup
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        # Wait for server to start with retries
        import time
        max_retries = 10
        retry_delay = 1
        
        for retry in range(max_retries):
            time.sleep(retry_delay)
            if check_mcp_server():
                logger.info(f"✓ OntServe MCP server started successfully (PID: {process.pid})")
                return True
            else:
                if retry < max_retries - 1:
                    logger.debug(f"Waiting for MCP server to be ready... ({retry + 1}/{max_retries})")
        
        # Final check
        if check_mcp_server():
            logger.info(f"✓ OntServe MCP server started successfully (PID: {process.pid})")
            return True
        else:
            logger.warning(f"MCP server process started (PID: {process.pid}) but not responding after {max_retries} seconds")
            logger.warning("The server may still be initializing. ProEthica will continue.")
            return False
            
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        return False

def main():
    """Main entry point for the ProEthica application."""
    # Check pipeline services (Redis, Celery)
    check_pipeline_services()

    # Check if MCP server integration should be skipped entirely
    skip_mcp = os.environ.get('SKIP_MCP', 'false').lower() == 'true'

    if skip_mcp:
        logger.info("MCP server integration disabled (SKIP_MCP=true)")
        os.environ['ONTSERVE_MCP_ENABLED'] = 'false'
    else:
        # Check OntServe MCP Server dependency
        mcp_port = int(os.environ.get('ONTSERVE_MCP_PORT', 8082))
        
        if not check_mcp_server(port=mcp_port):
            # Check if we should auto-start the MCP server
            auto_start_mcp = os.environ.get('AUTO_START_MCP', 'false').lower() == 'true'
            
            if auto_start_mcp:
                logger.info("Attempting to auto-start OntServe MCP server...")
                if start_mcp_server():
                    # Set environment variables for ProEthica
                    os.environ['ONTSERVE_MCP_ENABLED'] = 'true'
                    os.environ['ONTSERVE_MCP_URL'] = f'http://localhost:{mcp_port}'
                else:
                    logger.info("MCP server not available. ProEthica will run without ontology features.")
                    logger.info("To start MCP manually: cd ../OntServe && python servers/mcp_server.py")
                    os.environ['ONTSERVE_MCP_ENABLED'] = 'false'
            else:
                logger.info(f"MCP server not detected on port {mcp_port}. ProEthica will run without ontology features.")
                logger.info("To enable auto-start: export AUTO_START_MCP=true")
                logger.info("To skip this check: export SKIP_MCP=true")
                os.environ['ONTSERVE_MCP_ENABLED'] = 'false'
        else:
            logger.info(f"✓ OntServe MCP server detected on port {mcp_port}")
            os.environ['ONTSERVE_MCP_ENABLED'] = 'true'
            os.environ['ONTSERVE_MCP_URL'] = f'http://localhost:{mcp_port}'
    
    try:
        # Import the Flask app factory
        from app import create_app
        
        # Create the Flask application instance
        app = create_app()
        
        # Get configuration from environment variables
        # Default to debug=True in development (auto-reload on code changes)
        # Production uses gunicorn, so this only affects `python run.py`
        debug = os.environ.get('DEBUG', 'True').lower() == 'true'
        host = os.environ.get('FLASK_HOST', '0.0.0.0')
        port = int(os.environ.get('FLASK_PORT', 5000))
        
        # Log startup information
        logger.info(f"Starting ProEthica application...")
        logger.info(f"Debug mode: {debug}")
        logger.info(f"Host: {host}")
        logger.info(f"Port: {port}")
        
        # Run the Flask development server
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=debug,
            use_debugger=debug,
            exclude_patterns=[
                "*/tests/*",
                "*/docs-internal/*",
                "*/backups/*",
                "*.tmp.*",
            ] if debug else None,
        )
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Please ensure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        logger.error("Check your configuration and database settings")
        sys.exit(1)

if __name__ == '__main__':
    main()
