"""Enhanced Scenario Generation Configuration.

This module provides configuration management for the enhanced LLM-driven
scenario generation features, including feature flags and environment variables.
"""

import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class EnhancedScenarioConfig:
    """Configuration manager for enhanced scenario generation."""
    
    # Feature Flags
    ENHANCED_GENERATION_ENABLED = 'ENHANCED_SCENARIO_GENERATION'
    MCP_INTEGRATION_ENABLED = 'MCP_ONTOLOGY_INTEGRATION'
    LLM_REFINEMENT_ENABLED = 'ENHANCED_SCENARIO_LLM_REFINEMENT'
    
    # LLM Configuration
    LLM_PROVIDER = 'ENHANCED_SCENARIO_LLM_PROVIDER'  # anthropic, openai, google
    LLM_MODEL = 'ENHANCED_SCENARIO_LLM_MODEL'
    LLM_TEMPERATURE = 'ENHANCED_SCENARIO_LLM_TEMPERATURE'
    
    # Processing Limits
    MAX_TIMELINE_EVENTS = 'ENHANCED_SCENARIO_MAX_EVENTS'
    MAX_DECISIONS = 'ENHANCED_SCENARIO_MAX_DECISIONS'
    
    # MCP Server Configuration
    MCP_SERVER_URL = 'MCP_SERVER_URL'
    MCP_REQUEST_TIMEOUT = 'MCP_REQUEST_TIMEOUT'
    MCP_FALLBACK_ENABLED = 'MCP_FALLBACK_ENABLED'
    
    # Temporal Evidence Settings
    TEMPORAL_EVIDENCE_ENABLED = 'ENHANCED_SCENARIO_TEMPORAL_EVIDENCE'
    MIN_EVIDENCE_CONFIDENCE = 'ENHANCED_SCENARIO_MIN_EVIDENCE_CONFIDENCE'
    
    @classmethod
    def is_enhanced_generation_enabled(cls) -> bool:
        """Check if enhanced generation is enabled."""
        return os.environ.get(cls.ENHANCED_GENERATION_ENABLED, 'false').lower() == 'true'
    
    @classmethod
    def is_mcp_integration_enabled(cls) -> bool:
        """Check if MCP ontology integration is enabled."""
        return (
            cls.is_enhanced_generation_enabled() and 
            os.environ.get(cls.MCP_INTEGRATION_ENABLED, 'true').lower() == 'true'
        )
    
    @classmethod
    def is_llm_refinement_enabled(cls) -> bool:
        """Check if LLM refinement is enabled."""
        return (
            cls.is_enhanced_generation_enabled() and 
            os.environ.get(cls.LLM_REFINEMENT_ENABLED, 'true').lower() == 'true'
        )
    
    @classmethod
    def get_llm_config(cls) -> Dict[str, Any]:
        """Get LLM configuration settings."""
        return {
            'provider': os.environ.get(cls.LLM_PROVIDER, 'anthropic'),
            'model': os.environ.get(cls.LLM_MODEL, 'claude-sonnet-4-20250514'),
            'temperature': float(os.environ.get(cls.LLM_TEMPERATURE, '0.2')),
        }
    
    @classmethod
    def get_processing_limits(cls) -> Dict[str, int]:
        """Get processing limits configuration."""
        return {
            'max_timeline_events': int(os.environ.get(cls.MAX_TIMELINE_EVENTS, '20')),
            'max_decisions': int(os.environ.get(cls.MAX_DECISIONS, '8')),
        }
    
    @classmethod
    def get_mcp_config(cls) -> Dict[str, Any]:
        """Get MCP server configuration."""
        return {
            'server_url': os.environ.get(cls.MCP_SERVER_URL, 'http://localhost:5001'),
            'request_timeout': int(os.environ.get(cls.MCP_REQUEST_TIMEOUT, '10')),
            'fallback_enabled': os.environ.get(cls.MCP_FALLBACK_ENABLED, 'true').lower() == 'true',
        }
    
    @classmethod
    def get_temporal_evidence_config(cls) -> Dict[str, Any]:
        """Get temporal evidence configuration."""
        return {
            'enabled': os.environ.get(cls.TEMPORAL_EVIDENCE_ENABLED, 'true').lower() == 'true',
            'min_confidence': float(os.environ.get(cls.MIN_EVIDENCE_CONFIDENCE, '0.4')),
        }
    
    @classmethod
    def get_all_config(cls) -> Dict[str, Any]:
        """Get complete configuration dictionary."""
        return {
            'features': {
                'enhanced_generation': cls.is_enhanced_generation_enabled(),
                'mcp_integration': cls.is_mcp_integration_enabled(),
                'llm_refinement': cls.is_llm_refinement_enabled(),
            },
            'llm': cls.get_llm_config(),
            'processing': cls.get_processing_limits(),
            'mcp': cls.get_mcp_config(),
            'temporal_evidence': cls.get_temporal_evidence_config(),
        }
    
    @classmethod
    def validate_configuration(cls) -> Dict[str, Any]:
        """Validate configuration and return status."""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'config': cls.get_all_config()
        }
        
        # Check required API keys if enhanced generation is enabled
        if cls.is_enhanced_generation_enabled():
            llm_provider = cls.get_llm_config()['provider']
            
            if llm_provider == 'anthropic':
                if not os.environ.get('ANTHROPIC_API_KEY'):
                    validation_results['errors'].append('ANTHROPIC_API_KEY required for enhanced generation')
                    validation_results['valid'] = False
            
            elif llm_provider == 'openai':
                if not os.environ.get('OPENAI_API_KEY'):
                    validation_results['errors'].append('OPENAI_API_KEY required for enhanced generation')
                    validation_results['valid'] = False
        
        # Check MCP server accessibility if enabled
        if cls.is_mcp_integration_enabled():
            mcp_config = cls.get_mcp_config()
            if not mcp_config['fallback_enabled']:
                validation_results['warnings'].append('MCP fallback disabled - failures will cause errors')
        
        # Validate processing limits
        limits = cls.get_processing_limits()
        if limits['max_timeline_events'] > 50:
            validation_results['warnings'].append('High max_timeline_events may impact performance')
        
        if limits['max_decisions'] > 20:
            validation_results['warnings'].append('High max_decisions may impact processing time')
            
        return validation_results

    @classmethod 
    def log_configuration(cls):
        """Log current configuration for debugging."""
        config = cls.get_all_config()
        logger.info("Enhanced Scenario Generation Configuration:")
        logger.info(f"  Enhanced Generation: {config['features']['enhanced_generation']}")
        logger.info(f"  MCP Integration: {config['features']['mcp_integration']}")
        logger.info(f"  LLM Provider: {config['llm']['provider']}")
        logger.info(f"  MCP Server: {config['mcp']['server_url']}")
        logger.info(f"  Max Events: {config['processing']['max_timeline_events']}")
        logger.info(f"  Max Decisions: {config['processing']['max_decisions']}")


# Environment Variable Documentation
ENVIRONMENT_VARIABLES = {
    # Feature Control
    'ENHANCED_SCENARIO_GENERATION': {
        'description': 'Enable enhanced LLM-driven scenario generation',
        'type': 'boolean',
        'default': 'false',
        'examples': ['true', 'false']
    },
    'MCP_ONTOLOGY_INTEGRATION': {
        'description': 'Enable MCP server ontology integration',
        'type': 'boolean',
        'default': 'true',
        'examples': ['true', 'false']
    },
    'ENHANCED_SCENARIO_LLM_REFINEMENT': {
        'description': 'Enable LLM refinement of decisions',
        'type': 'boolean',
        'default': 'true',
        'examples': ['true', 'false']
    },
    
    # LLM Configuration
    'ENHANCED_SCENARIO_LLM_PROVIDER': {
        'description': 'LLM provider for scenario generation',
        'type': 'string',
        'default': 'anthropic',
        'examples': ['anthropic', 'openai', 'google']
    },
    'ENHANCED_SCENARIO_LLM_MODEL': {
        'description': 'Specific LLM model to use',
        'type': 'string',
        'default': 'claude-sonnet-4-20250514',
        'examples': ['claude-sonnet-4-20250514', 'claude-opus-4-1-20250805', 'gpt-4', 'gemini-pro']
    },
    'ENHANCED_SCENARIO_LLM_TEMPERATURE': {
        'description': 'Temperature for LLM generation (0.0-1.0)',
        'type': 'float',
        'default': '0.2',
        'examples': ['0.1', '0.2', '0.5']
    },
    
    # Processing Limits
    'ENHANCED_SCENARIO_MAX_EVENTS': {
        'description': 'Maximum number of timeline events to extract',
        'type': 'integer',
        'default': '20',
        'examples': ['15', '20', '25']
    },
    'ENHANCED_SCENARIO_MAX_DECISIONS': {
        'description': 'Maximum number of decisions to generate',
        'type': 'integer',
        'default': '8',
        'examples': ['5', '8', '12']
    },
    
    # MCP Server
    'MCP_SERVER_URL': {
        'description': 'URL of the MCP ontology server',
        'type': 'string',
        'default': 'http://localhost:5001',
        'examples': ['http://localhost:5001', 'https://mcp.proethica.org']
    },
    'MCP_REQUEST_TIMEOUT': {
        'description': 'Timeout for MCP requests in seconds',
        'type': 'integer',
        'default': '10',
        'examples': ['5', '10', '30']
    },
    'MCP_FALLBACK_ENABLED': {
        'description': 'Enable fallback when MCP server is unavailable',
        'type': 'boolean',
        'default': 'true',
        'examples': ['true', 'false']
    },
    
    # Temporal Evidence
    'ENHANCED_SCENARIO_TEMPORAL_EVIDENCE': {
        'description': 'Enable temporal evidence extraction for ordering',
        'type': 'boolean',
        'default': 'true',
        'examples': ['true', 'false']
    },
    'ENHANCED_SCENARIO_MIN_EVIDENCE_CONFIDENCE': {
        'description': 'Minimum confidence threshold for temporal evidence',
        'type': 'float',
        'default': '0.4',
        'examples': ['0.3', '0.4', '0.6']
    },
    
    # Required API Keys (when enabled)
    'ANTHROPIC_API_KEY': {
        'description': 'Anthropic API key for Claude models',
        'type': 'string',
        'required_when': 'ENHANCED_SCENARIO_LLM_PROVIDER=anthropic',
        'sensitive': True
    },
    'OPENAI_API_KEY': {
        'description': 'OpenAI API key for GPT models',
        'type': 'string',
        'required_when': 'ENHANCED_SCENARIO_LLM_PROVIDER=openai',
        'sensitive': True
    }
}


def generate_env_template() -> str:
    """Generate environment variable template for documentation."""
    template_lines = [
        "# Enhanced Scenario Generation Configuration",
        "# =========================================",
        "",
        "# Enable enhanced LLM-driven scenario generation",
        "# Set to 'true' to activate all enhanced features",
        "ENHANCED_SCENARIO_GENERATION=false",
        "",
        "# LLM Configuration",
        "ENHANCED_SCENARIO_LLM_PROVIDER=anthropic",
        "ENHANCED_SCENARIO_LLM_MODEL=claude-sonnet-4-20250514",
        "ENHANCED_SCENARIO_LLM_TEMPERATURE=0.2",
        "",
        "# Processing Limits",
        "ENHANCED_SCENARIO_MAX_EVENTS=20",
        "ENHANCED_SCENARIO_MAX_DECISIONS=8",
        "",
        "# MCP Server Configuration",
        "MCP_SERVER_URL=http://localhost:5001",
        "MCP_REQUEST_TIMEOUT=10",
        "MCP_FALLBACK_ENABLED=true",
        "",
        "# API Keys (required when enhanced generation enabled)",
        "# ANTHROPIC_API_KEY=your_key_here",
        "# OPENAI_API_KEY=your_key_here",
        ""
    ]
    
    return "\n".join(template_lines)


# Quick access functions
def is_enhanced_enabled() -> bool:
    """Quick check if enhanced generation is enabled."""
    return EnhancedScenarioConfig.is_enhanced_generation_enabled()

def get_config() -> Dict[str, Any]:
    """Quick access to full configuration."""
    return EnhancedScenarioConfig.get_all_config()

def validate_config() -> Dict[str, Any]:
    """Quick configuration validation."""
    return EnhancedScenarioConfig.validate_configuration()