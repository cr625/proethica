#!/usr/bin/env python3
"""
ProEthica Monitoring Script

Standalone script for monitoring ProEthica service health.
Can be run manually or via cron job.

Usage:
    # Run once
    python scripts/monitor.py

    # Cron job (every 5 minutes)
    */5 * * * * /opt/proethica/venv/bin/python /opt/proethica/scripts/monitor.py

Environment variables:
    PROETHICA_URL: Base URL for ProEthica (default: http://localhost:5000)
    MONITOR_LOG_FILE: Log file path (default: /var/log/proethica/monitor.log)
    ALERT_THRESHOLD: Consecutive failures before alerting (default: 2)
"""

import os
import sys
import json
import time
import logging
import argparse
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for imports
script_dir = Path(__file__).parent
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))
sys.path.insert(0, str(project_dir.parent))

# Load environment from .env
from dotenv import load_dotenv
load_dotenv(project_dir / '.env')

# Configure logging
log_file = os.environ.get('MONITOR_LOG_FILE', '/var/log/proethica/monitor.log')
log_dir = Path(log_file).parent

# Create log directory if it doesn't exist (fall back to /tmp if no permissions)
try:
    log_dir.mkdir(parents=True, exist_ok=True)
except PermissionError:
    log_file = '/tmp/proethica_monitor.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
PROETHICA_URL = os.environ.get('PROETHICA_URL', 'http://localhost:5000')
ONTSERVE_URL = os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
ALERT_THRESHOLD = int(os.environ.get('ALERT_THRESHOLD', '2'))

# State file for tracking consecutive failures
STATE_FILE = Path('/tmp/proethica_monitor_state.json')


def load_state() -> Dict[str, int]:
    """Load failure count state from file."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load state file: {e}")
    return {}


def save_state(state: Dict[str, int]):
    """Save failure count state to file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"Could not save state file: {e}")


def check_http(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Check HTTP endpoint health.

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        Dict with status, latency_ms, and optional error
    """
    try:
        import urllib.request
        import urllib.error

        start = time.time()
        req = urllib.request.Request(url, headers={'User-Agent': 'ProEthica-Monitor/1.0'})
        response = urllib.request.urlopen(req, timeout=timeout)
        latency = (time.time() - start) * 1000

        status_code = response.getcode()
        if status_code == 200:
            return {'status': 'up', 'latency_ms': round(latency, 2), 'http_code': status_code}
        else:
            return {'status': 'degraded', 'latency_ms': round(latency, 2), 'http_code': status_code}

    except urllib.error.HTTPError as e:
        return {'status': 'down', 'error': f'HTTP {e.code}', 'http_code': e.code}
    except urllib.error.URLError as e:
        return {'status': 'down', 'error': str(e.reason)}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_socket(host: str, port: int, timeout: int = 5) -> Dict[str, Any]:
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        result = sock.connect_ex((host, port))
        latency = (time.time() - start) * 1000
        sock.close()

        if result == 0:
            return {'status': 'up', 'latency_ms': round(latency, 2)}
        return {'status': 'down', 'error': 'Connection refused'}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_redis() -> Dict[str, Any]:
    """Check Redis service."""
    try:
        result = subprocess.run(
            ['redis-cli', 'ping'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and 'PONG' in result.stdout:
            return {'status': 'up'}
        return {'status': 'down', 'error': result.stderr or 'No PONG response'}
    except FileNotFoundError:
        # redis-cli not available, try socket
        return check_socket('localhost', 6379)
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_celery() -> Dict[str, Any]:
    """Check Celery workers by looking for running processes."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'celery.*worker'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return {'status': 'up', 'workers': len(pids)}
        return {'status': 'down', 'error': 'No celery workers found'}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_postgresql() -> Dict[str, Any]:
    """Check PostgreSQL database."""
    try:
        db_pass = os.environ.get('PGPASSWORD', 'PASS')
        result = subprocess.run(
            ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'ai_ethical_dm', '-c', 'SELECT 1;'],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, 'PGPASSWORD': db_pass}
        )
        if result.returncode == 0:
            return {'status': 'up'}
        return {'status': 'down', 'error': result.stderr[:100] if result.stderr else 'Unknown error'}
    except FileNotFoundError:
        # psql not available, try socket
        return check_socket('localhost', 5432)
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_gunicorn() -> Dict[str, Any]:
    """Check Gunicorn/Flask process."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'gunicorn.*proethica'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return {'status': 'up', 'workers': len(pids)}
        return {'status': 'down', 'error': 'No gunicorn workers found'}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def run_checks() -> Dict[str, Dict[str, Any]]:
    """Run all health checks and return results."""
    results = {}

    # Core services
    logger.info("Checking core services...")
    results['postgresql'] = check_postgresql()
    results['redis'] = check_redis()
    results['celery'] = check_celery()

    # Application endpoints
    logger.info("Checking application endpoints...")
    results['proethica_health'] = check_http(f"{PROETHICA_URL}/health")
    results['proethica_ready'] = check_http(f"{PROETHICA_URL}/health/ready")

    # External services
    logger.info("Checking external services...")
    results['ontserve_mcp'] = check_socket('localhost', 8082)

    return results


def send_alert(title: str, message: str, level: str = 'error'):
    """Send alert via the alerting module."""
    try:
        from app.utils.alerting import send_alert as _send_alert, AlertLevel
        level_map = {
            'info': AlertLevel.INFO,
            'warning': AlertLevel.WARNING,
            'error': AlertLevel.ERROR,
            'critical': AlertLevel.CRITICAL,
        }
        return _send_alert(title, message, level=level_map.get(level, AlertLevel.ERROR))
    except ImportError:
        logger.error(f"ALERT [{level.upper()}]: {title} - {message}")
        return False
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def process_results(results: Dict[str, Dict[str, Any]]) -> bool:
    """
    Process check results and send alerts if needed.

    Returns:
        True if all checks passed, False otherwise
    """
    state = load_state()
    all_healthy = True
    alerts_sent = []

    for service, result in results.items():
        status = result.get('status', 'unknown')
        is_healthy = status == 'up'

        if is_healthy:
            # Clear failure count on recovery
            if state.get(service, 0) > 0:
                logger.info(f"{service} recovered")
                # Send recovery notification if we previously alerted
                if state[service] >= ALERT_THRESHOLD:
                    send_alert(
                        f"{service} Recovered",
                        f"The {service} service has recovered and is now healthy.",
                        level='info'
                    )
            state[service] = 0
        else:
            all_healthy = False
            state[service] = state.get(service, 0) + 1
            logger.warning(f"{service} is {status}: {result.get('error', 'Unknown')}")

            # Send alert if threshold reached
            if state[service] == ALERT_THRESHOLD:
                error_msg = result.get('error', 'Service is not responding')
                send_alert(
                    f"{service} Service Down",
                    f"The {service} service has failed {ALERT_THRESHOLD} consecutive checks.\n\nError: {error_msg}",
                    level='critical' if service in ['postgresql', 'proethica_health'] else 'error'
                )
                alerts_sent.append(service)

    save_state(state)

    # Log summary
    healthy_count = sum(1 for r in results.values() if r.get('status') == 'up')
    logger.info(f"Health check complete: {healthy_count}/{len(results)} services healthy")

    if alerts_sent:
        logger.warning(f"Alerts sent for: {', '.join(alerts_sent)}")

    return all_healthy


def ping_healthchecks_io():
    """Ping Healthchecks.io to signal the monitor is running."""
    url = os.environ.get('HEALTHCHECKS_PING_URL')
    if not url:
        return

    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=10)
        logger.debug("Healthchecks.io ping sent")
    except Exception as e:
        logger.warning(f"Failed to ping Healthchecks.io: {e}")


def main():
    parser = argparse.ArgumentParser(description='ProEthica Monitoring Script')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    parser.add_argument('--no-alert', action='store_true', help='Disable alerting')
    parser.add_argument('--test-alert', action='store_true', help='Send test alert and exit')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.test_alert:
        logger.info("Sending test alert...")
        success = send_alert(
            "Test Alert",
            "This is a test alert from the ProEthica monitoring script.",
            level='info'
        )
        sys.exit(0 if success else 1)

    logger.info(f"Starting health check (URL: {PROETHICA_URL})")
    start_time = time.time()

    # Run all checks
    results = run_checks()

    # Process results and send alerts
    if not args.no_alert:
        all_healthy = process_results(results)
    else:
        all_healthy = all(r.get('status') == 'up' for r in results.values())

    # Calculate duration
    duration = time.time() - start_time

    # Add summary to results
    results['_summary'] = {
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'duration_ms': round(duration * 1000, 2),
        'all_healthy': all_healthy,
        'hostname': socket.gethostname()
    }

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"ProEthica Health Check - {results['_summary']['timestamp']}")
        print(f"{'='*50}")
        for service, result in results.items():
            if service.startswith('_'):
                continue
            status = result.get('status', 'unknown')
            icon = '[OK]' if status == 'up' else '[!!]' if status == 'down' else '[??]'
            extra = ''
            if 'latency_ms' in result:
                extra = f" ({result['latency_ms']}ms)"
            elif 'workers' in result:
                extra = f" ({result['workers']} workers)"
            elif 'error' in result:
                extra = f" - {result['error'][:40]}"
            print(f"  {icon} {service}: {status}{extra}")
        print(f"{'='*50}")
        print(f"Duration: {results['_summary']['duration_ms']}ms")
        print()

    # Ping Healthchecks.io to signal we're running
    ping_healthchecks_io()

    # Exit with appropriate code
    sys.exit(0 if all_healthy else 1)


if __name__ == '__main__':
    main()
