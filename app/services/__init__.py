# Import services to make them available when importing from app.services
from app.services.event_engine import EventEngine
from app.services.decision_engine import DecisionEngine
from app.services.mcp_client import MCPClient
# Import embedding service conditionally to avoid circular imports
# This approach allows Triple to import db without causing circular imports
# EmbeddingService is still available through lazy import in modules that need it
from app.services.enhanced_decision_engine import EnhancedDecisionEngine
from app.services.rdf_service import RDFService

# Use a function for conditional importing to avoid circular dependencies
def get_embedding_service():
    from app.services.embedding_service import EmbeddingService
    return EmbeddingService

# Use a function for conditional importing of EntityTripleService to avoid circular dependencies
def get_entity_triple_service():
    from app.services.entity_triple_service import EntityTripleService
    return EntityTripleService

# Use a function for conditional importing of RDFSerializationService to avoid circular dependencies
def get_rdf_serialization_service():
    from app.services.rdf_serialization_service import RDFSerializationService
    return RDFSerializationService
