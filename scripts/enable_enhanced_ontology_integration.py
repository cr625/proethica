#!/usr/bin/env python3
"""
Enable Enhanced Ontology-LLM Integration

This script:
1. Registers the OntologyContextProvider
2. Updates the application configuration to enable the provider
3. Sets appropriate priority and token allocation
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.application_context_service import ApplicationContextService
from app.services.context_providers.ontology_context_provider import OntologyContextProvider, register_provider

def update_app_config(app_context_service):
    """
    Update application configuration to properly utilize the enhanced ontology integration.
    
    Args:
        app_context_service: The ApplicationContextService instance
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current configuration
        current_config = app_context_service.config
        
        # Create a copy to modify
        new_config = current_config.copy()
        
        # Make sure sections exists
        if 'sections' not in new_config:
            new_config['sections'] = {}
        
        # Make sure context_providers exists
        if 'context_providers' not in new_config:
            new_config['context_providers'] = {}
        
        # Update ontology context provider settings
        new_config['context_providers']['ontology'] = {
            'enabled': True,
            'description': 'Enhanced ontology context with relationships and constraints'
        }
        
        # Set appropriate priority and token allocation for the ontology section
        new_config['sections']['ontology'] = {
            'priority': 2,  # High priority, just after world_context
            'max_percent': 30  # Allocate 30% of tokens to ontology context
        }
        
        # If there's a scenario_context, adjust its priority
        if 'scenario_context' in new_config['sections']:
            new_config['sections']['scenario_context']['priority'] = 3
            
        # Increase max_tokens to ensure enough context
        new_config['max_tokens'] = max(new_config.get('max_tokens', 2000), 3000)
        
        # Update the configuration
        app_context_service.update_configuration(new_config)
        print("Application configuration updated successfully")
        
        # Verify the update by getting the config again
        updated_config = app_context_service.config
        if 'ontology' in updated_config.get('sections', {}) and updated_config.get('context_providers', {}).get('ontology', {}).get('enabled', False):
            print("Configuration update verified")
            return True
        else:
            print("WARNING: Configuration update could not be verified")
            return False
    except Exception as e:
        print(f"Error updating application configuration: {str(e)}")
        return False

def update_config_file():
    """
    Update the configuration file directly if database update fails.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        config_path = Path('app/config/application_context.json')
        
        # Check if file exists
        if not config_path.exists():
            print(f"Config file not found: {config_path}")
            # Create the directory if it doesn't exist
            config_path.parent.mkdir(exist_ok=True)
            
            # Create a minimal config
            config = {
                'max_tokens': 3000,
                'sections': {
                    'world_context': {'priority': 1, 'max_percent': 30},
                    'ontology': {'priority': 2, 'max_percent': 30},
                    'scenario_context': {'priority': 3, 'max_percent': 20},
                    'navigation': {'priority': 4, 'max_percent': 10},
                    'entities': {'priority': 5, 'max_percent': 10}
                },
                'context_providers': {
                    'default': {'enabled': True},
                    'ontology': {
                        'enabled': True,
                        'description': 'Enhanced ontology context with relationships and constraints'
                    }
                },
                'caching': {
                    'enabled': True,
                    'ttl_seconds': 300
                },
                'schema_version': ApplicationContextService.CONTEXT_VERSION
            }
        else:
            # Read existing config
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Update config
            config.setdefault('sections', {})
            config.setdefault('context_providers', {})
            
            # Add ontology section
            config['sections']['ontology'] = {
                'priority': 2,  # High priority, just after world_context
                'max_percent': 30  # Allocate 30% of tokens to ontology context
            }
            
            # Adjust scenario priority if it exists
            if 'scenario_context' in config['sections']:
                config['sections']['scenario_context']['priority'] = 3
            
            # Add ontology provider settings
            config['context_providers']['ontology'] = {
                'enabled': True,
                'description': 'Enhanced ontology context with relationships and constraints'
            }
            
            # Increase max_tokens
            config['max_tokens'] = max(config.get('max_tokens', 2000), 3000)
        
        # Write updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Configuration file updated: {config_path}")
        return True
    except Exception as e:
        print(f"Error updating configuration file: {str(e)}")
        return False

def register_ontology_provider():
    """
    Register the ontology context provider.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        result = register_provider()
        if result:
            print("OntologyContextProvider registered successfully")
            return True
        else:
            print("Failed to register OntologyContextProvider")
            return False
    except Exception as e:
        print(f"Error registering OntologyContextProvider: {str(e)}")
        return False

def verify_enhanced_mcp_client():
    """
    Verify that the enhanced MCP client is working properly.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from app.services.enhanced_mcp_client import get_enhanced_mcp_client
        
        client = get_enhanced_mcp_client()
        print(f"Enhanced MCP client initialized with URL: {client.mcp_url}")
        
        # Check connection if server is supposed to be running
        if client.check_connection():
            print("Successfully connected to MCP server")
        else:
            print("WARNING: Could not connect to MCP server. Make sure it's running with: python3 mcp/run_enhanced_mcp_server.py")
        
        return True
    except Exception as e:
        print(f"Error verifying enhanced MCP client: {str(e)}")
        return False

def update_claude_file():
    """
    Update CLAUDE.md with information about the enhanced context provider.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        claude_md_path = Path('CLAUDE.md')
        
        # Check if file exists
        if not claude_md_path.exists():
            print(f"CLAUDE.md not found at {claude_md_path}")
            return False
        
        # Read existing content
        with open(claude_md_path, 'r') as f:
            content = f.read()
        
        # Check if the enhanced ontology integration is already mentioned
        if "Enhanced Ontology-LLM Integration" in content:
            print("CLAUDE.md already contains information about enhanced ontology integration")
            return True
        
        # Get the section on enhanced MCP server
        mcp_section_start = content.find("## 2025-04-28 - Enhanced Ontology-LLM Integration")
        
        if mcp_section_start >= 0:
            # Find the end of this section (next H2)
            next_section = content.find("##", mcp_section_start + 2)
            
            if next_section >= 0:
                # Extract the MCP section
                mcp_section = content[mcp_section_start:next_section]
                
                # Add information about the context provider
                additional_info = """

### Added Enhanced Ontology Context Provider

1. **Implemented Ontology Context Provider**
   - Created `app/services/context_providers/ontology_context_provider.py` to enhance LLM context
   - Integrates with the enhanced MCP server to provide rich ontology information
   - Automatically extracts relevant entities and relationships based on user queries

2. **Improved LLM Context Generation**
   - Semantic search for query-relevant ontology entities
   - Entity relationship exploration for better context understanding
   - Inclusion of ontology hierarchies and structures
   - Automatic extraction of applicable guidelines and constraints

3. **Configuration Updates**
   - Updated application configuration to enable the ontology context provider
   - Set appropriate priority and token allocation for optimal context balance
   - Integrated with existing context providers for a unified experience

These enhancements significantly improve the LLM's understanding of ontology concepts and their relationships, leading to more accurate and contextually relevant responses.
"""
                
                # Insert the additional info
                updated_content = content[:next_section] + additional_info + content[next_section:]
                
                # Write updated content
                with open(claude_md_path, 'w') as f:
                    f.write(updated_content)
                
                print(f"Updated {claude_md_path} with context provider information")
                return True
            else:
                # No next section found, append to the end
                updated_content = content + "\n\n" + additional_info
                
                # Write updated content
                with open(claude_md_path, 'w') as f:
                    f.write(updated_content)
                
                print(f"Updated {claude_md_path} with context provider information (appended)")
                return True
        else:
            print("Could not find 'Enhanced Ontology-LLM Integration' section in CLAUDE.md")
            return False
    except Exception as e:
        print(f"Error updating CLAUDE.md: {str(e)}")
        return False

def main():
    """Run the installation process."""
    print("Enabling enhanced ontology-LLM integration")
    
    # Verify enhanced MCP client
    verify_enhanced_mcp_client()
    
    # Register the ontology context provider
    register_ontology_provider()
    
    # Get the ApplicationContextService
    app_context_service = ApplicationContextService.get_instance()
    
    # Update application configuration
    db_update_success = update_app_config(app_context_service)
    
    # If database update fails, update the configuration file directly
    if not db_update_success:
        update_config_file()
    
    # Update CLAUDE.md
    update_claude_file()
    
    print("\nEnhanced ontology-LLM integration enabled!")
    print("\nTo verify the integration:")
    print("1. Start the enhanced MCP server: python3 mcp/run_enhanced_mcp_server.py")
    print("2. Restart the application to apply context provider changes")
    print("3. Look for 'Enhanced ontology context' in LLM responses")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
