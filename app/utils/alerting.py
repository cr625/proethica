"""
Unified alerting system for ProEthica monitoring.

Uses Apprise library for flexible notification delivery.
Supports email (SMTP), Slack, Telegram, and 90+ other services.

Configuration via environment variables:
- ALERT_EMAIL_ENABLED: Enable email alerts (true/false)
- ALERT_SMTP_HOST: SMTP server hostname
- ALERT_SMTP_PORT: SMTP server port (default: 587)
- ALERT_SMTP_USER: SMTP username
- ALERT_SMTP_PASS: SMTP password
- ALERT_EMAIL_FROM: Sender email address
- ALERT_EMAIL_TO: Recipient email address(es), comma-separated
- ALERT_RATE_LIMIT: Seconds between alerts of same type (default: 300)
"""

import os
import time
import logging
import hashlib
from datetime import datetime
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Rate limiting cache: {alert_key: last_sent_timestamp}
_rate_limit_cache = {}

# Default rate limit: 5 minutes between same alerts
DEFAULT_RATE_LIMIT = 300


class AlertLevel:
    """Alert severity levels."""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


def get_alert_config():
    """Get alerting configuration from environment."""
    return {
        'email_enabled': os.environ.get('ALERT_EMAIL_ENABLED', 'false').lower() == 'true',
        'smtp_host': os.environ.get('ALERT_SMTP_HOST', ''),
        'smtp_port': int(os.environ.get('ALERT_SMTP_PORT', '587')),
        'smtp_user': os.environ.get('ALERT_SMTP_USER', ''),
        'smtp_pass': os.environ.get('ALERT_SMTP_PASS', ''),
        'email_from': os.environ.get('ALERT_EMAIL_FROM', 'alerts@proethica.org'),
        'email_to': os.environ.get('ALERT_EMAIL_TO', ''),
        'rate_limit': int(os.environ.get('ALERT_RATE_LIMIT', str(DEFAULT_RATE_LIMIT))),
    }


def is_rate_limited(alert_key: str, rate_limit: int = None) -> bool:
    """
    Check if an alert is rate limited.

    Args:
        alert_key: Unique key for this alert type
        rate_limit: Seconds between alerts (default from config)

    Returns:
        True if alert should be suppressed
    """
    config = get_alert_config()
    limit = rate_limit or config['rate_limit']

    now = time.time()
    last_sent = _rate_limit_cache.get(alert_key, 0)

    if now - last_sent < limit:
        logger.debug(f"Alert rate limited: {alert_key}")
        return True

    return False


def mark_alert_sent(alert_key: str):
    """Mark an alert as sent for rate limiting."""
    _rate_limit_cache[alert_key] = time.time()


def generate_alert_key(title: str, message: str) -> str:
    """Generate a unique key for rate limiting based on alert content."""
    content = f"{title}:{message[:100]}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def send_alert(
    title: str,
    message: str,
    level: str = AlertLevel.WARNING,
    rate_limit: int = None,
    force: bool = False
) -> bool:
    """
    Send an alert notification.

    Args:
        title: Alert title/subject
        message: Alert body message
        level: Alert severity (info, warning, error, critical)
        rate_limit: Override rate limit for this alert
        force: Bypass rate limiting

    Returns:
        True if alert was sent, False if rate limited or failed
    """
    config = get_alert_config()

    # Generate alert key for rate limiting
    alert_key = generate_alert_key(title, message)

    # Check rate limiting (unless forced)
    if not force and is_rate_limited(alert_key, rate_limit):
        return False

    # Check if any alerting is enabled
    if not config['email_enabled']:
        logger.info(f"Alerting disabled, would send: [{level.upper()}] {title}")
        return False

    success = False

    # Try to send via Apprise
    try:
        import apprise

        apobj = apprise.Apprise()

        # Configure email if enabled
        if config['email_enabled'] and config['smtp_host'] and config['email_to']:
            # Build Apprise email URL
            # Format: mailtos://user:password@smtp_host:port/?to=recipient
            email_url = _build_email_url(config)
            if email_url:
                apobj.add(email_url)

        if len(apobj) == 0:
            logger.warning("No alert channels configured")
            return False

        # Format the message
        formatted_body = _format_alert_body(title, message, level)

        # Map level to Apprise notification type
        notify_type = apprise.NotifyType.WARNING
        if level == AlertLevel.INFO:
            notify_type = apprise.NotifyType.INFO
        elif level == AlertLevel.ERROR:
            notify_type = apprise.NotifyType.FAILURE
        elif level == AlertLevel.CRITICAL:
            notify_type = apprise.NotifyType.FAILURE

        # Send notification
        success = apobj.notify(
            title=f"[ProEthica] {title}",
            body=formatted_body,
            notify_type=notify_type
        )

        if success:
            mark_alert_sent(alert_key)
            logger.info(f"Alert sent: [{level.upper()}] {title}")
        else:
            logger.error(f"Failed to send alert: {title}")

    except ImportError:
        logger.warning("Apprise not installed, falling back to logging")
        logger.error(f"ALERT [{level.upper()}]: {title} - {message}")
        success = False
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        success = False

    return success


def _build_email_url(config: dict) -> Optional[str]:
    """Build Apprise email URL from configuration."""
    try:
        host = config['smtp_host']
        port = config['smtp_port']
        user = config['smtp_user']
        password = config['smtp_pass']
        sender = config['email_from']
        recipients = config['email_to']

        if not all([host, recipients]):
            return None

        from urllib.parse import quote

        # URL encode user and password (handle spaces and special chars)
        encoded_user = quote(user, safe='') if user else ''
        encoded_pass = quote(password, safe='') if password else ''

        # Build the URL
        # For Gmail port 587: use mailtos:// with mode=starttls
        # Format: mailtos://user:password@host:port?from=sender&to=recipient&mode=starttls
        if encoded_user and encoded_pass:
            auth = f"{encoded_user}:{encoded_pass}@"
        else:
            auth = ""

        url = f"mailtos://{auth}{host}:{port}"
        url += f"?from={quote(sender, safe='@.')}"
        url += f"&to={quote(recipients, safe='@.,')}"

        # Add mode=starttls for port 587 (Gmail, most modern SMTP)
        if port == 587:
            url += "&mode=starttls"

        logger.debug(f"Built email URL for {host}:{port} -> {recipients}")
        return url
    except Exception as e:
        logger.error(f"Error building email URL: {e}")
        return None


def _format_alert_body(title: str, message: str, level: str) -> str:
    """Format alert body with timestamp and metadata."""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    hostname = os.environ.get('HOSTNAME', 'unknown')

    body = f"""
{message}

---
Timestamp: {timestamp}
Severity: {level.upper()}
Host: {hostname}
Service: ProEthica

This is an automated alert from the ProEthica monitoring system.
""".strip()

    return body


def send_service_alert(service_name: str, status: str, details: str = ""):
    """
    Send alert for service health issues.

    Args:
        service_name: Name of the service (redis, celery, mcp, etc.)
        status: Current status (down, degraded, etc.)
        details: Additional details about the issue
    """
    level = AlertLevel.ERROR if status == 'down' else AlertLevel.WARNING

    title = f"{service_name.upper()} Service {status.title()}"
    message = f"The {service_name} service is currently {status}."

    if details:
        message += f"\n\nDetails:\n{details}"

    return send_alert(title, message, level=level)


def send_error_alert(error: Exception, context: str = ""):
    """
    Send alert for application errors.

    Args:
        error: The exception that occurred
        context: Additional context (e.g., route, request info)
    """
    title = f"Application Error: {type(error).__name__}"
    message = f"An error occurred in the application.\n\nError: {str(error)}"

    if context:
        message += f"\n\nContext:\n{context}"

    return send_alert(title, message, level=AlertLevel.ERROR)


def send_demo_alert(issue: str, details: str = ""):
    """
    Send alert for demo-related issues (higher priority during demo period).

    Args:
        issue: Description of the issue
        details: Additional details
    """
    title = f"Demo Issue: {issue}"
    message = f"A demo-related issue has been detected.\n\n{issue}"

    if details:
        message += f"\n\nDetails:\n{details}"

    # Demo alerts have shorter rate limit (1 minute)
    return send_alert(title, message, level=AlertLevel.CRITICAL, rate_limit=60)


def clear_rate_limits():
    """Clear all rate limit entries (for testing)."""
    global _rate_limit_cache
    _rate_limit_cache = {}
    logger.info("Alert rate limits cleared")


def test_alerting():
    """
    Test the alerting configuration by sending a test alert.
    Returns True if alert was sent successfully.
    """
    return send_alert(
        title="Test Alert",
        message="This is a test alert from ProEthica monitoring system. If you receive this, alerting is configured correctly.",
        level=AlertLevel.INFO,
        force=True  # Bypass rate limiting for test
    )
