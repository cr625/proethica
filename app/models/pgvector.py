"""
Shared PostgreSQL pgvector type for SQLAlchemy models.
"""

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """PostgreSQL vector type via pgvector extension."""
    cache_ok = True

    def __init__(self, dim=384):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return f"[{','.join(str(x) for x in value)}]"
            return value
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                return [float(x) for x in value[1:-1].split(',')]
            return value
        return process
