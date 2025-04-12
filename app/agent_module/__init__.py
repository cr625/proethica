"""
Agent module for ProEthica.

This module provides a modular agent implementation that can be used
with ProEthica and other applications.
"""

from typing import Dict, Any, Optional, Union

from app.agent_module.interfaces.base import (
    SourceInterface,
    ContextProviderInterface,
    LLMInterface,
    AuthInterface,
    SessionInterface
)
from app.agent_module.services.auth import (
    FlaskLoginAuthAdapter, 
    DefaultAuthProvider,
    ConfigurableAuthProvider
)
from app.agent_module.services.session import FlaskSessionManager, MemorySessionManager
from app.agent_module.models.conversation import Conversation, Message
from app.agent_module.blueprints.agent import create_agent_blueprint


def create_proethica_agent_blueprint(
    config: Optional[Dict[str, Any]] = None,
    url_prefix: str = '/agent',
    template_folder: Optional[str] = None,
    static_folder: Optional[str] = None,
    blueprint_name: str = 'agent'
):
    """
    Create an agent blueprint for ProEthica with authentication enabled.
    
    This is a convenience function that uses ProEthica's existing services.
    
    Args:
        config: Configuration dictionary (optional)
        url_prefix: URL prefix for the blueprint
        template_folder: Template folder for the blueprint
        static_folder: Static folder for the blueprint
        blueprint_name: Name for the blueprint
        
    Returns:
        Flask blueprint
    """
    from app.agent_module.adapters.proethica import (
        WorldSourceAdapter,
        ApplicationContextAdapter,
        ClaudeServiceAdapter
    )
    import os
    
    # Default config
    cfg = {
        'require_auth': True,
        'api_key': os.environ.get('ANTHROPIC_API_KEY'),
        'use_claude': True
    }
    
    # Update config if provided
    if config:
        cfg.update(config)
    
    # Create adapters
    source_interface = WorldSourceAdapter()
    context_provider = ApplicationContextAdapter()
    
    # Create LLM service
    if cfg.get('use_claude', True):
        llm_interface = ClaudeServiceAdapter(api_key=cfg.get('api_key'))
    else:
        from app.agent_module.adapters.proethica import LLMServiceAdapter
        llm_interface = LLMServiceAdapter()
    
    # Create auth interface
    if cfg.get('require_auth', True):
        auth_interface = FlaskLoginAuthAdapter()
    else:
        auth_interface = DefaultAuthProvider()
    
    # Create session interface
    session_interface = FlaskSessionManager()
    
    # Create blueprint
    return create_agent_blueprint(
        source_interface=source_interface,
        context_provider=context_provider,
        llm_interface=llm_interface,
        auth_interface=auth_interface,
        session_interface=session_interface,
        require_auth=cfg.get('require_auth', True),
        url_prefix=url_prefix,
        template_folder=template_folder,
        static_folder=static_folder,
        blueprint_name=blueprint_name
    )


# Export primary classes and functions
__all__ = [
    'create_agent_blueprint',
    'create_proethica_agent_blueprint',
    'Conversation',
    'Message',
    'SourceInterface',
    'ContextProviderInterface',
    'LLMInterface',
    'AuthInterface',
    'SessionInterface',
    'FlaskLoginAuthAdapter',
    'DefaultAuthProvider',
    'ConfigurableAuthProvider',
    'FlaskSessionManager',
    'MemorySessionManager'
]
