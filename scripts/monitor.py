#!/usr/bin/env python3
"""
ProEthica Local Health Check

Runs via cron every 5 minutes. Checks internal services and logs results
for post-incident diagnostics. External alerting is handled by UptimeRobot.

Usage:
    python scripts/monitor.py
    python scripts/monitor.py --json
    python scripts/monitor.py -v

Cron:
    */5 * * * * /opt/proethica/venv/bin/python /opt/proethica/scripts/monitor.py
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
from typing import Dict, Any

script_dir = Path(__file__).parent
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))

from dotenv import load_dotenv
load_dotenv(project_dir / '.env')

log_file = os.environ.get('MONITOR_LOG_FILE', '/var/log/proethica/monitor.log')
try:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
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

PROETHICA_URL = os.environ.get('PROETHICA_URL', 'http://localhost:5000')


def check_http(url: str, timeout: int = 10) -> Dict[str, Any]:
    """Check HTTP endpoint health."""
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


def check_process(pattern: str) -> Dict[str, Any]:
    """Check if a process matching pattern is running."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', pattern],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return {'status': 'up', 'workers': len(pids)}
        return {'status': 'down', 'error': 'No process found'}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_postgresql() -> Dict[str, Any]:
    """Check PostgreSQL database."""
    try:
        db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', '')
        if 'postgresql://' in db_uri:
            from urllib.parse import urlparse
            parsed = urlparse(db_uri)
            db_user = parsed.username or 'postgres'
            db_pass = parsed.password or 'PASS'
            db_name = parsed.path.lstrip('/') or 'ai_ethical_dm'
            db_host = parsed.hostname or 'localhost'
        else:
            db_user, db_pass = 'postgres', 'PASS'
            db_name, db_host = 'ai_ethical_dm', 'localhost'

        result = subprocess.run(
            ['psql', '-h', db_host, '-U', db_user, '-d', db_name, '-c', 'SELECT 1;'],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, 'PGPASSWORD': db_pass}
        )
        if result.returncode == 0:
            return {'status': 'up'}
        return {'status': 'down', 'error': result.stderr[:100] if result.stderr else 'Unknown error'}
    except FileNotFoundError:
        return check_socket('localhost', 5432)
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def run_checks() -> Dict[str, Dict[str, Any]]:
    """Run all health checks."""
    results = {}
    results['postgresql'] = check_postgresql()
    results['redis'] = check_socket('localhost', 6379)
    results['celery'] = check_process('celery.*worker')
    results['proethica_health'] = check_http(f"{PROETHICA_URL}/health")
    results['proethica_ready'] = check_http(f"{PROETHICA_URL}/health/ready")
    results['ontserve_mcp'] = check_socket('localhost', 8082)
    return results


def main():
    parser = argparse.ArgumentParser(description='ProEthica Local Health Check')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Starting health check (URL: {PROETHICA_URL})")
    start_time = time.time()

    results = run_checks()

    all_healthy = all(r.get('status') == 'up' for r in results.values())
    for service, result in results.items():
        if result.get('status') != 'up':
            logger.warning(f"{service} is {result.get('status')}: {result.get('error', 'Unknown')}")

    healthy_count = sum(1 for r in results.values() if r.get('status') == 'up')
    logger.info(f"Health check complete: {healthy_count}/{len(results)} services healthy")

    duration = time.time() - start_time
    results['_summary'] = {
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'duration_ms': round(duration * 1000, 2),
        'all_healthy': all_healthy,
        'hostname': socket.gethostname()
    }

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

    sys.exit(0 if all_healthy else 1)


if __name__ == '__main__':
    main()
