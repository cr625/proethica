# Import services to make them available when importing from app.services
from app.services.mcp_client import MCPClient
# Import embedding service conditionally to avoid circular imports
# This approach allows Triple to import db without causing circular imports
# EmbeddingService is still available through lazy import in modules that need it

# Use a function for conditional importing to avoid circular dependencies
def get_embedding_service():
    from app.services.embedding_service import EmbeddingService
    return EmbeddingService

# Use a function for conditional importing of EntityTripleService to avoid circular dependencies
def get_entity_triple_service():
    from app.services.entity_triple_service import EntityTripleService
    return EntityTripleService

from app.services import temporal_context_service_enhancements
