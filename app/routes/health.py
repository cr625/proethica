"""
Health check endpoints for monitoring and alerting.

Provides multiple levels of health checks:
- /health - Fast liveness probe (always returns 200 if app is running)
- /health/ready - Readiness probe (checks all dependencies)
- /health/services - Detailed service status for Uptime Kuma
- /health/demo - Tests demo-critical routes (cases 4-15)
"""

import logging
import time
import socket
from flask import Blueprint, jsonify, current_app, request
from functools import wraps
from app.utils.environment_auth import admin_required_production

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__, url_prefix='/health')


def init_health_csrf_exemption(app):
    """Exempt health API routes from CSRF protection."""
    if hasattr(app, 'csrf'):
        from app.routes.health import test_alert, clear_errors, test_error, clear_activities
        app.csrf.exempt(test_alert)
        app.csrf.exempt(clear_errors)
        app.csrf.exempt(test_error)
        app.csrf.exempt(clear_activities)

# Cache for health check results (avoid hammering services)
_health_cache = {
    'ready': {'result': None, 'timestamp': 0},
    'services': {'result': None, 'timestamp': 0},
}
CACHE_TTL_SUCCESS = 30  # Cache successful results for 30 seconds
CACHE_TTL_FAILURE = 10  # Cache failures for 10 seconds


def cached_health_check(check_name, ttl_success=CACHE_TTL_SUCCESS, ttl_failure=CACHE_TTL_FAILURE):
    """Decorator to cache health check results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = _health_cache.get(check_name, {'result': None, 'timestamp': 0})
            now = time.time()

            # Check if cached result is still valid
            if cache['result'] is not None:
                cached_data, cached_code = cache['result']
                # Determine health from HTTP code (200 = healthy)
                is_healthy = cached_code == 200
                ttl = ttl_success if is_healthy else ttl_failure
                if now - cache['timestamp'] < ttl:
                    # Return cached response
                    return jsonify(cached_data), cached_code

            # Execute the health check
            result = func(*args, **kwargs)

            # Cache the result - extract data from tuple (jsonify response, status_code)
            if isinstance(result, tuple) and len(result) == 2:
                response, status_code = result
                # Get JSON data from response
                if hasattr(response, 'get_json'):
                    data = response.get_json()
                else:
                    data = response
                _health_cache[check_name] = {'result': (data, status_code), 'timestamp': now}

            return result
        return wrapper
    return decorator


def check_database():
    """Check PostgreSQL database connection."""
    try:
        from app.models import db
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'up', 'latency_ms': 0}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {'status': 'down', 'error': str(e)}


def check_redis():
    """Check Redis connection."""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=1, socket_timeout=2)
        start = time.time()
        r.ping()
        latency = (time.time() - start) * 1000
        return {'status': 'up', 'latency_ms': round(latency, 2)}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {'status': 'down', 'error': str(e)}


def check_celery():
    """Check Celery worker availability."""
    try:
        from celery_config import celery
        inspect = celery.control.inspect(timeout=2)
        active = inspect.active()
        if active:
            worker_count = len(active)
            return {'status': 'up', 'workers': worker_count}
        return {'status': 'down', 'error': 'No active workers'}
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return {'status': 'down', 'error': str(e)}


def check_mcp():
    """Check OntServe MCP server."""
    try:
        mcp_url = current_app.config.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
        # Extract host and port from URL
        from urllib.parse import urlparse
        parsed = urlparse(mcp_url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 8082

        # Simple socket connection test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        start = time.time()
        result = sock.connect_ex((host, port))
        latency = (time.time() - start) * 1000
        sock.close()

        if result == 0:
            return {'status': 'up', 'latency_ms': round(latency, 2)}
        return {'status': 'down', 'error': 'Connection refused'}
    except Exception as e:
        logger.error(f"MCP health check failed: {e}")
        return {'status': 'down', 'error': str(e)}


def check_demo_case(case_id):
    """Check if a demo case is accessible."""
    try:
        from app.models.document import Document
        doc = Document.query.get(case_id)
        if doc:
            return {'status': 'up', 'title': doc.title[:50] if doc.title else 'Untitled'}
        return {'status': 'down', 'error': 'Case not found'}
    except Exception as e:
        logger.error(f"Demo case {case_id} check failed: {e}")
        return {'status': 'down', 'error': str(e)}


@health_bp.route('')
@health_bp.route('/')
def liveness():
    """
    Fast liveness probe.
    Returns 200 if the application is running.
    Used by load balancers and container orchestrators.
    """
    return jsonify({
        'status': 'healthy',
        'app': 'ProEthica',
        'environment': current_app.config.get('ENVIRONMENT', 'unknown')
    }), 200


@health_bp.route('/ready')
@cached_health_check('ready')
def readiness():
    """
    Readiness probe - checks all critical dependencies.
    Returns 200 if all services are healthy, 503 if any are down.
    """
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'celery': check_celery(),
        'mcp': check_mcp(),
    }

    # Determine overall status
    all_up = all(c['status'] == 'up' for c in checks.values())
    critical_up = checks['database']['status'] == 'up'  # DB is critical

    if all_up:
        status = 'healthy'
        http_code = 200
    elif critical_up:
        status = 'degraded'
        http_code = 200  # Still serve traffic if DB is up
    else:
        status = 'unhealthy'
        http_code = 503

    return jsonify({
        'status': status,
        'checks': checks,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }), http_code


@health_bp.route('/services')
@cached_health_check('services')
def services():
    """
    Detailed service status for monitoring dashboards.
    Includes more detail than /ready for debugging.
    """
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'celery': check_celery(),
        'mcp': check_mcp(),
    }

    # Add system info
    import os
    system_info = {
        'hostname': socket.gethostname(),
        'pid': os.getpid(),
        'environment': current_app.config.get('ENVIRONMENT', 'unknown'),
    }

    # Determine overall status
    all_up = all(c['status'] == 'up' for c in checks.values())

    return jsonify({
        'status': 'healthy' if all_up else 'degraded',
        'services': checks,
        'system': system_info,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }), 200 if all_up else 503


@health_bp.route('/demo')
@admin_required_production
def demo():
    """
    Test all extracted cases (cases with extraction prompts).
    Returns status for each case and overall health.
    """
    from app.models import db

    # Get cases that have extraction data
    try:
        result = db.session.execute(
            db.text("SELECT DISTINCT case_id FROM extraction_prompts WHERE case_id IS NOT NULL ORDER BY case_id")
        )
        demo_case_ids = [row[0] for row in result]
    except Exception as e:
        logger.error(f"Failed to get case list: {e}")
        # Fallback to known range
        demo_case_ids = list(range(4, 27))

    results = {}
    for case_id in demo_case_ids:
        results[f'case_{case_id}'] = check_demo_case(case_id)

    # Count healthy cases
    healthy_count = sum(1 for r in results.values() if r['status'] == 'up')
    total_count = len(demo_case_ids)

    # Primary demo case (7) must be healthy
    primary_healthy = results.get('case_7', {}).get('status') == 'up'

    if healthy_count == total_count:
        status = 'healthy'
    elif primary_healthy and healthy_count >= total_count // 2:
        status = 'degraded'
    else:
        status = 'unhealthy'

    return jsonify({
        'status': status,
        'healthy_cases': healthy_count,
        'total_cases': total_count,
        'primary_case_7': 'up' if primary_healthy else 'down',
        'cases': results,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }), 200 if status != 'unhealthy' else 503


@health_bp.route('/clear-cache')
@admin_required_production
def clear_cache():
    """Clear health check cache (for testing)."""
    global _health_cache
    _health_cache = {
        'ready': {'result': None, 'timestamp': 0},
        'services': {'result': None, 'timestamp': 0},
    }
    return jsonify({'message': 'Cache cleared'}), 200


@health_bp.route('/status')
@admin_required_production
def status_page():
    """
    Visual status page for monitoring.
    Displays real-time service health in a dashboard format.
    """
    from flask import render_template
    return render_template('health/status.html')


@health_bp.route('/test-alert', methods=['POST'])
@admin_required_production
def test_alert():
    """
    Send a test alert to verify alerting configuration.
    """
    try:
        from app.utils.alerting import test_alerting
        success = test_alerting()
        if success:
            return jsonify({'success': True, 'message': 'Test alert sent successfully'}), 200
        else:
            return jsonify({'success': False, 'message': 'Alert not sent (check configuration)'}), 200
    except Exception as e:
        logger.error(f"Test alert failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@health_bp.route('/errors')
@admin_required_production
def errors():
    """
    Get recent errors as JSON.
    """
    try:
        from app.utils.error_tracker import get_recent_errors, get_error_stats
        limit = request.args.get('limit', 50, type=int)
        return jsonify({
            'errors': get_recent_errors(limit=limit),
            'stats': get_error_stats()
        }), 200
    except Exception as e:
        logger.error(f"Error fetching errors: {e}")
        return jsonify({'error': str(e)}), 500


@health_bp.route('/errors/clear', methods=['POST'])
@admin_required_production
def clear_errors():
    """
    Clear the error log (for testing).
    """
    try:
        from app.utils.error_tracker import clear_errors as _clear_errors
        _clear_errors()
        return jsonify({'message': 'Error log cleared'}), 200
    except Exception as e:
        logger.error(f"Error clearing errors: {e}")
        return jsonify({'error': str(e)}), 500


@health_bp.route('/errors/test', methods=['POST'])
@admin_required_production
def test_error():
    """
    Generate a test error to verify error tracking and alerting.
    """
    # This will trigger the 500 error handler
    raise Exception("Test error triggered from /health/errors/test")


@health_bp.route('/activities')
@admin_required_production
def activities():
    """
    Get recent user activities as JSON.
    """
    try:
        from app.utils.activity_tracker import get_recent_activities, get_activity_stats
        limit = request.args.get('limit', 50, type=int)
        category = request.args.get('category')
        return jsonify({
            'activities': get_recent_activities(limit=limit, category=category),
            'stats': get_activity_stats()
        }), 200
    except Exception as e:
        logger.error(f"Error fetching activities: {e}")
        return jsonify({'error': str(e)}), 500


@health_bp.route('/activities/clear', methods=['POST'])
@admin_required_production
def clear_activities():
    """
    Clear the activity log (for testing).
    """
    try:
        from app.utils.activity_tracker import clear_activities as _clear_activities
        _clear_activities()
        return jsonify({'message': 'Activity log cleared'}), 200
    except Exception as e:
        logger.error(f"Error clearing activities: {e}")
        return jsonify({'error': str(e)}), 500
