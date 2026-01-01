"""
Activity tracking for ProEthica.

Captures user actions in memory for display in the admin dashboard.
Tracks page views, document operations, pipeline actions, and auth events.
"""

import logging
from datetime import datetime, timezone
from collections import deque
from typing import Optional, Dict, Any, List
from threading import Lock

logger = logging.getLogger(__name__)

# In-memory activity store (last 500 actions)
MAX_ACTIVITIES = 500
_activity_store: deque = deque(maxlen=MAX_ACTIVITIES)
_activity_lock = Lock()

# Activity counts by type
_activity_counts: Dict[str, int] = {}


class ActivityRecord:
    """Represents a captured user action."""

    def __init__(
        self,
        action: str,
        category: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        path: str = "",
        method: str = "",
        details: Optional[Dict[str, Any]] = None,
        remote_addr: str = ""
    ):
        self.timestamp = datetime.now(timezone.utc)
        self.action = action
        self.category = category  # auth, document, pipeline, admin, page_view
        self.user_id = user_id
        self.username = username
        self.path = path
        self.method = method
        self.details = details or {}
        self.remote_addr = remote_addr

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'category': self.category,
            'user_id': self.user_id,
            'username': self.username,
            'path': self.path,
            'method': self.method,
            'details': self.details,
            'remote_addr': self.remote_addr
        }


def log_activity(
    action: str,
    category: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    path: str = "",
    method: str = "",
    details: Optional[Dict[str, Any]] = None,
    remote_addr: str = ""
) -> ActivityRecord:
    """
    Log a user activity.

    Args:
        action: Description of the action (e.g., "Viewed case 7", "Login")
        category: Category of action (auth, document, pipeline, admin, page_view)
        user_id: ID of the user performing the action
        username: Username of the user
        path: Request path
        method: HTTP method
        details: Additional context
        remote_addr: Client IP address

    Returns:
        The created ActivityRecord
    """
    record = ActivityRecord(
        action=action,
        category=category,
        user_id=user_id,
        username=username,
        path=path,
        method=method,
        details=details,
        remote_addr=remote_addr
    )

    with _activity_lock:
        _activity_store.append(record)
        _activity_counts[category] = _activity_counts.get(category, 0) + 1

    logger.debug(f"Activity: [{category}] {action} by {username or 'anonymous'}")
    return record


def get_recent_activities(limit: int = 50, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get recent activities as a list of dictionaries.

    Args:
        limit: Maximum number of activities to return
        category: Filter by category (optional)

    Returns:
        List of activity dictionaries, newest first
    """
    with _activity_lock:
        if category:
            activities = [a for a in _activity_store if a.category == category]
        else:
            activities = list(_activity_store)

        # Get last N and reverse (newest first)
        activities = activities[-limit:]
        activities.reverse()
        return [a.to_dict() for a in activities]


def get_activity_stats() -> Dict[str, Any]:
    """
    Get activity statistics.

    Returns:
        Dictionary with activity counts and stats
    """
    with _activity_lock:
        total = len(_activity_store)
        by_category = dict(_activity_counts)

        # Count activities in last hour
        now = datetime.now(timezone.utc)
        last_hour = sum(
            1 for a in _activity_store
            if (now - a.timestamp).total_seconds() < 3600
        )

        # Get unique users in last hour
        unique_users = set(
            a.user_id for a in _activity_store
            if a.user_id and (now - a.timestamp).total_seconds() < 3600
        )

        # Most recent activity time
        last_activity = None
        if _activity_store:
            last_activity = _activity_store[-1].timestamp.isoformat()

        return {
            'total_captured': total,
            'last_hour': last_hour,
            'unique_users_last_hour': len(unique_users),
            'by_category': by_category,
            'last_activity_at': last_activity,
            'max_stored': MAX_ACTIVITIES
        }


def clear_activities():
    """Clear all stored activities (for testing)."""
    global _activity_counts
    with _activity_lock:
        _activity_store.clear()
        _activity_counts = {}
    logger.info("Activity store cleared")
