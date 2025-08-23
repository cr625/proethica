"""
OntServe Configuration for ProEthica

Environment-based configuration for OntServe integration,
enabling gradual migration from ProEthica's internal ontology serving.
"""

import os
from typing import Dict, Optional

# Environment-based configuration
ONTSERVE_ENABLED = os.environ.get('USE_ONTSERVE', 'false').lower() in ('true', '1', 'yes')
ONTSERVE_WEB_URL = os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')  # REST API endpoint
ONTSERVE_MCP_URL = os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8083')  # Future MCP endpoint
ONTSERVE_TIMEOUT = int(os.environ.get('ONTSERVE_TIMEOUT', 30))

# Debug and logging
ONTSERVE_DEBUG = os.environ.get('ONTSERVE_DEBUG', 'false').lower() in ('true', '1', 'yes')

# World to Domain mapping configuration
# Maps ProEthica world.ontology_id to OntServe domain names
WORLD_DOMAIN_MAPPING: Dict[int, str] = {
    1: 'engineering-ethics',      # Engineering World (Primary domain)
    2: 'proethica-intermediate',  # Intermediate concepts ontology
    3: 'bfo',                     # Basic Formal Ontology
    # Add more mappings as needed
}

# Reverse mapping for domain to world lookup
DOMAIN_WORLD_MAPPING: Dict[str, int] = {
    domain: world_id for world_id, domain in WORLD_DOMAIN_MAPPING.items()
}

def get_domain_for_world(world_id: int) -> Optional[str]:
    """
    Get OntServe domain name for a ProEthica world ID.
    
    Args:
        world_id: ProEthica world.ontology_id
        
    Returns:
        OntServe domain name or None if not mapped
    """
    return WORLD_DOMAIN_MAPPING.get(world_id)

def get_world_for_domain(domain_name: str) -> Optional[int]:
    """
    Get ProEthica world ID for an OntServe domain name.
    
    Args:
        domain_name: OntServe domain name
        
    Returns:
        ProEthica world ID or None if not mapped
    """
    return DOMAIN_WORLD_MAPPING.get(domain_name)

def is_ontserve_enabled() -> bool:
    """Check if OntServe integration is enabled."""
    return ONTSERVE_ENABLED

def get_ontserve_config() -> Dict[str, any]:
    """
    Get complete OntServe configuration.
    
    Returns:
        Configuration dictionary
    """
    return {
        'enabled': ONTSERVE_ENABLED,
        'web_url': ONTSERVE_WEB_URL,
        'mcp_url': ONTSERVE_MCP_URL,
        'timeout': ONTSERVE_TIMEOUT,
        'debug': ONTSERVE_DEBUG,
        'world_domain_mapping': WORLD_DOMAIN_MAPPING,
        'domain_world_mapping': DOMAIN_WORLD_MAPPING,
    }

# Configuration validation
def validate_ontserve_config() -> bool:
    """
    Validate OntServe configuration.
    
    Returns:
        True if configuration is valid
    """
    if not ONTSERVE_ENABLED:
        return True  # No validation needed if disabled
    
    if not ONTSERVE_WEB_URL:
        print("ERROR: ONTSERVE_WEB_URL not configured but USE_ONTSERVE=true")
        return False
    
    if not WORLD_DOMAIN_MAPPING:
        print("WARNING: No world-to-domain mappings configured")
    
    return True

# Auto-validate on import
if not validate_ontserve_config():
    print("OntServe configuration validation failed!")