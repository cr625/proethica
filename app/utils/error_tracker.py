"""
Error tracking for ProEthica.

Captures application errors in memory for display in the status dashboard.
Also provides hooks for alerting on errors.
"""

import logging
import traceback
from datetime import datetime, timezone
from collections import deque
from typing import Optional, Dict, Any, List
from threading import Lock

logger = logging.getLogger(__name__)

# In-memory error store (last 100 errors)
MAX_ERRORS = 100
_error_store: deque = deque(maxlen=MAX_ERRORS)
_error_lock = Lock()

# Error counts by type (for rate limiting and stats)
_error_counts: Dict[str, int] = {}


class ErrorRecord:
    """Represents a captured error."""

    def __init__(
        self,
        error: Exception,
        path: str = "",
        method: str = "",
        user_id: Optional[int] = None,
        remote_addr: str = "",
        extra: Optional[Dict[str, Any]] = None
    ):
        self.timestamp = datetime.now(timezone.utc)
        self.error_type = type(error).__name__
        self.error_message = str(error)
        self.traceback = traceback.format_exc()
        self.path = path
        self.method = method
        self.user_id = user_id
        self.remote_addr = remote_addr
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'error_type': self.error_type,
            'error_message': self.error_message[:500],  # Truncate long messages
            'path': self.path,
            'method': self.method,
            'user_id': self.user_id,
            'remote_addr': self.remote_addr,
            'traceback': self.traceback[:2000] if self.traceback else None,  # Truncate
            'extra': self.extra
        }


def capture_error(
    error: Exception,
    path: str = "",
    method: str = "",
    user_id: Optional[int] = None,
    remote_addr: str = "",
    extra: Optional[Dict[str, Any]] = None,
    send_alert: bool = True
) -> ErrorRecord:
    """
    Capture an error for tracking and optional alerting.

    Args:
        error: The exception that occurred
        path: Request path (e.g., /cases/7/structure)
        method: HTTP method (GET, POST, etc.)
        user_id: ID of logged-in user, if any
        remote_addr: Client IP address
        extra: Additional context to store
        send_alert: Whether to send an alert for this error

    Returns:
        The created ErrorRecord
    """
    record = ErrorRecord(
        error=error,
        path=path,
        method=method,
        user_id=user_id,
        remote_addr=remote_addr,
        extra=extra
    )

    # Store in memory
    with _error_lock:
        _error_store.append(record)
        _error_counts[record.error_type] = _error_counts.get(record.error_type, 0) + 1

    # Log the error
    logger.error(
        f"Captured error: {record.error_type} on {method} {path}: {record.error_message}",
        exc_info=True
    )

    # Send alert if enabled
    if send_alert:
        try:
            from app.utils.alerting import send_error_alert
            context = f"Path: {path}\nMethod: {method}"
            if remote_addr:
                context += f"\nIP: {remote_addr}"
            if user_id:
                context += f"\nUser ID: {user_id}"
            send_error_alert(error, context)
        except Exception as alert_error:
            logger.warning(f"Failed to send error alert: {alert_error}")

    return record


def get_recent_errors(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent errors as a list of dictionaries.

    Args:
        limit: Maximum number of errors to return

    Returns:
        List of error dictionaries, newest first
    """
    with _error_lock:
        # Convert to list and reverse (newest first)
        errors = list(_error_store)[-limit:]
        errors.reverse()
        return [e.to_dict() for e in errors]


def get_error_stats() -> Dict[str, Any]:
    """
    Get error statistics.

    Returns:
        Dictionary with error counts and stats
    """
    with _error_lock:
        total = len(_error_store)
        by_type = dict(_error_counts)

        # Count errors in last hour
        now = datetime.now(timezone.utc)
        last_hour = sum(
            1 for e in _error_store
            if (now - e.timestamp).total_seconds() < 3600
        )

        # Get most recent error time
        last_error = None
        if _error_store:
            last_error = _error_store[-1].timestamp.isoformat()

        return {
            'total_captured': total,
            'last_hour': last_hour,
            'by_type': by_type,
            'last_error_at': last_error,
            'max_stored': MAX_ERRORS
        }


def clear_errors():
    """Clear all stored errors (for testing)."""
    global _error_counts
    with _error_lock:
        _error_store.clear()
        _error_counts = {}
    logger.info("Error store cleared")
