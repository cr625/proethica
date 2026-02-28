"""
PostgreSQL pgvector type for SQLAlchemy models.
Uses the pgvector Python package for native distance operator support.
"""

from pgvector.sqlalchemy import Vector

__all__ = ["Vector"]
