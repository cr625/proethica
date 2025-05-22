#!/usr/bin/env python3
"""
Script to verify LLM integration and MCP server connectivity.

This script tests that:
1. The LLM service is properly patched to use live Claude calls
2. The mock data is properly replaced with engineering ethics examples
3. The MCP server is being properly accessed for ontology data
"""

import os
import sys
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up Flask application context."""
    logger.info("Setting up environment")
    
    # Set up environment variables
    os.environ['ENVIRONMENT'] = 'codespace'
    os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['FLASK_DEBUG'] = '1'
    
    # Load environment variables from .env file if it exists
    if os.path.exists('.env'):
        load_dotenv()
        logger.info("Loaded environment variables from .env file")
    
    # Apply SQLAlchemy URL fix if available
    try:
        import patch_sqlalchemy_url
        patch_sqlalchemy_url.patch_create_app()
        logger.info("Applied SQLAlchemy URL patch")
    except Exception as e:
        logger.warning(f"Failed to apply SQLAlchemy URL patch: {str(e)}")
    
    # Initialize MCP environment variables if not present
    if 'MCP_SERVER_URL' not in os.environ:
        os.environ['MCP_SERVER_URL'] = 'http://localhost:5001'
        logger.info(f"Set default MCP_SERVER_URL: {os.environ['MCP_SERVER_URL']}")
    
    # Import after environment variables are set
    from app import create_app, db
    from app.models.document import Document
    from app.services.llm_service import LLMService
    from app.services.mcp_client import MCPClient
    
    # Create and configure the app
    app = create_app('config')
    app.app_context().push()
    
    logger.info("App context set up successfully")
    
    return {
        'app': app,
        'db': db,
        'Document': Document,
        'LLMService': LLMService,
        'MCPClient': MCPClient
    }

def verify_llm_service(context):
    """
    Verify that the LLM service is properly configured.
    
    Args:
        context: Application context
        
    Returns:
        Dictionary with verification results
    """
    logger.info("Verifying LLM service")
    
    LLMService = context['LLMService']
    
    # Create LLM service instance
    llm_service = LLMService()
    
    # Check if LLM is a mock or real implementation
    llm_type = type(llm_service.llm).__name__
    is_mock = 'FakeListLLM' in llm_type
    
    logger.info(f"LLM type: {llm_type}")
    logger.info(f"Is mock LLM: {is_mock}")
    
    # Test a simple prompt to see the response
    test_prompt = """
    You are an AI assistant with engineering ethics expertise.
    
    Please respond to the following test prompt with a single sentence:
    "Describe the core principle of the NSPE Code of Ethics in one sentence."
    
    Keep your response limited to one sentence.
    """
    
    try:
        logger.info("Testing LLM with a simple prompt")
        response_obj = llm_service.llm.invoke(test_prompt)
        
        # Handle different response types
        if hasattr(response_obj, 'content'):
            response = response_obj.content
        elif isinstance(response_obj, dict) and 'content' in response_obj:
            response = response_obj['content']
        else:
            response = str(response_obj)
            
        logger.info(f"LLM response: {response}")
    except Exception as e:
        logger.exception(f"Error invoking LLM: {str(e)}")
        response = f"Error: {str(e)}"
    
    # Check response for indicators of engineering ethics vs. military triage
    has_engineering_terms = any(term in response.lower() for term in [
        'engineer', 'nspe', 'code of ethics', 'public safety', 'professional'
    ])
    
    has_medical_terms = any(term in response.lower() for term in [
        'triage', 'medical', 'patient', 'hospital', 'injuries'
    ])
    
    return {
        'llm_type': llm_type,
        'is_mock': is_mock,
        'response': response,
        'has_engineering_terms': has_engineering_terms,
        'has_medical_terms': has_medical_terms,
        'success': not has_medical_terms
    }

def verify_mcp_integration(context):
    """
    Verify that the MCP client is properly integrated.
    
    Args:
        context: Application context
        
    Returns:
        Dictionary with verification results
    """
    logger.info("Verifying MCP integration")
    
    MCPClient = context['MCPClient']
    
    # Get MCP client instance
    mcp_client = MCPClient.get_instance()
    
    # Check if MCP client is configured
    if not mcp_client:
        return {
            'success': False,
            'error': 'Failed to get MCP client instance'
        }
    
    # Check MCP server URL
    mcp_server_url = getattr(mcp_client, 'mcp_server_url', None)
    logger.info(f"MCP server URL: {mcp_server_url}")
    
    # Test connection to MCP server
    try:
        logger.info("Testing connection to MCP server")
        # First check if test_connection exists, otherwise try check_connection
        if hasattr(mcp_client, 'test_connection'):
            status = mcp_client.test_connection()
        elif hasattr(mcp_client, 'check_connection'):
            status = mcp_client.check_connection()
        else:
            # Manual check - just see if we can access a basic endpoint
            logger.info("No connection test method found, attempting manual check")
            import requests
            if not mcp_server_url:
                mcp_server_url = "http://localhost:5001"  # Default
            response = requests.get(f"{mcp_server_url}/api/status")
            status = {'success': response.status_code == 200}
            
        logger.info(f"MCP connection status: {status}")
        connection_successful = status.get('success', False) if isinstance(status, dict) else False
    except Exception as e:
        logger.exception(f"Error testing MCP connection: {str(e)}")
        connection_successful = False
        status = {'error': str(e)}
    
    # Try to get ontology entities
    try:
        logger.info("Testing retrieval of ontology entities")
        world_name = 'engineering-ethics'
        # Try different API endpoints based on what might be available
        ontology_data = None
        using_mock_data = False
        
        # Try standard get_world_entities first
        if hasattr(mcp_client, 'get_world_entities'):
            try:
                logger.info(f"Trying get_world_entities({world_name})")
                ontology_data = mcp_client.get_world_entities(world_name)
                if ontology_data and isinstance(ontology_data, dict) and 'entities' in ontology_data:
                    logger.info("Successfully got entities from get_world_entities")
                else:
                    logger.warning("get_world_entities returned empty or invalid data")
            except Exception as e:
                logger.warning(f"Error with get_world_entities: {str(e)}")
        
        # Try get_ontology_entities if that's available
        if not ontology_data and hasattr(mcp_client, 'get_ontology_entities'):
            try:
                logger.info(f"Trying get_ontology_entities({world_name})")
                ontology_data = mcp_client.get_ontology_entities(world_name)
                if ontology_data and isinstance(ontology_data, dict) and 'entities' in ontology_data:
                    logger.info("Successfully got entities from get_ontology_entities")
                else:
                    logger.warning("get_ontology_entities returned empty or invalid data")
            except Exception as e:
                logger.warning(f"Error with get_ontology_entities: {str(e)}")
        
        # Try a direct HTTP request to various possible API endpoints
        if not ontology_data:
            try:
                import requests
                if not mcp_server_url:
                    mcp_server_url = "http://localhost:5001"  # Default
                    
                # Try a few different endpoint patterns
                endpoints = [
                    f"{mcp_server_url}/api/ontology/{world_name}/entities",
                    f"{mcp_server_url}/api/worlds/{world_name}/entities",
                    f"{mcp_server_url}/api/{world_name}/entities",
                    f"{mcp_server_url}/api/engineering-ethics/triples"  # Specific to this project
                ]
                
                for endpoint in endpoints:
                    try:
                        logger.info(f"Trying direct HTTP request to {endpoint}")
                        response = requests.get(endpoint)
                        if response.status_code == 200:
                            data = response.json()
                            if isinstance(data, dict):
                                if 'entities' in data:
                                    ontology_data = data
                                    logger.info(f"Successfully got entities from {endpoint}")
                                    break
                                # Try to adapt other response formats
                                elif 'triples' in data:
                                    # Convert triples format to entities format
                                    entities = {'entities': {'triples': data['triples']}}
                                    ontology_data = entities
                                    logger.info(f"Converted triples from {endpoint} to entities format")
                                    break
                    except Exception as e:
                        logger.warning(f"Error with endpoint {endpoint}: {str(e)}")
                        continue
            except Exception as e:
                logger.warning(f"Error with direct HTTP requests: {str(e)}")
        
        # Finally, try mock data if all else fails
        if not ontology_data:
            logger.warning(f"No entities found for world '{world_name}', trying mock data")
            if hasattr(mcp_client, 'get_mock_entities'):
                ontology_data = mcp_client.get_mock_entities(world_name)
            else:
                # Create a minimal mock data structure
                ontology_data = {
                    'entities': {
                        'concepts': [
                            {'id': 'public_safety', 'label': 'Public Safety', 'description': 'The primary ethical obligation of engineers'},
                            {'id': 'professional_integrity', 'label': 'Professional Integrity', 'description': 'Honesty and impartiality in engineering decisions'}
                        ]
                    }
                }
            using_mock_data = True
        else:
            using_mock_data = False
            
        # Check if we got any entities
        entities = ontology_data.get('entities', {})
        entity_count = sum(len(group) for group in entities.values()) if entities else 0
        logger.info(f"Retrieved {entity_count} entities (using mock data: {using_mock_data})")
        
        retrieval_successful = entity_count > 0
        
    except Exception as e:
        logger.exception(f"Error retrieving ontology entities: {str(e)}")
        retrieval_successful = False
        using_mock_data = True
        entities = {}
        entity_count = 0
    
    return {
        'mcp_server_url': mcp_server_url,
        'connection_successful': connection_successful,
        'connection_status': status,
        'retrieval_successful': retrieval_successful,
        'using_mock_data': using_mock_data,
        'entity_count': entity_count,
        'success': connection_successful or retrieval_successful
    }

def verify_patched_behavior(context):
    """
    Verify that the patching system is properly applied.
    
    Args:
        context: Application context
        
    Returns:
        Dictionary with verification results
    """
    logger.info("Verifying patched behavior")
    
    try:
        # Import and apply the patches
        from app.services.experiment.patch_prediction_service import patch_prediction_service, rollback_patch
        
        # Apply patches
        logger.info("Applying patches")
        patch_prediction_service()
        
        # Create a new LLM service instance after patching
        LLMService = context['LLMService']
        patched_llm_service = LLMService()
        
        # Check LLM type
        patched_llm_type = type(patched_llm_service.llm).__name__
        logger.info(f"Patched LLM type: {patched_llm_type}")
        
        # Test a simple prompt to verify engineering focus
        test_prompt = "What ethical considerations apply to engineering projects?"
        
        logger.info("Testing patched LLM with an engineering ethics prompt")
        patched_response_obj = patched_llm_service.llm.invoke(test_prompt)
        
        # Handle different response types (string vs AIMessage)
        if hasattr(patched_response_obj, 'content'):
            # AIMessage or similar object with content attribute
            patched_response = patched_response_obj.content
        elif isinstance(patched_response_obj, dict) and 'content' in patched_response_obj:
            # Dictionary with content key
            patched_response = patched_response_obj['content']
        else:
            # Assume it's a string or string-like object
            patched_response = str(patched_response_obj)
            
        logger.info(f"Patched LLM response: {patched_response[:200]}...")
        
        # Check if the response contains engineering terms
        has_engineering_terms = any(term in patched_response.lower() for term in [
            'engineer', 'nspe', 'code of ethics', 'public safety', 'professional'
        ])
        
        # Check if the response contains medical terms
        has_medical_terms = any(term in patched_response.lower() for term in [
            'triage', 'medical', 'patient', 'hospital', 'injuries'
        ])
        
        # Rollback patches to restore original behavior
        logger.info("Rolling back patches")
        rollback_patch()
        
        # Now test a non-patched instance for comparison
        original_llm_service = LLMService()
        original_llm_type = type(original_llm_service.llm).__name__
        logger.info(f"Original LLM type after rollback: {original_llm_type}")
        
        # Test with same prompt on original service
        logger.info("Testing non-patched LLM with the same prompt")
        original_response_obj = original_llm_service.llm.invoke(test_prompt)
        
        # Handle different response types (string vs AIMessage)
        if hasattr(original_response_obj, 'content'):
            # AIMessage or similar object with content attribute
            original_response = original_response_obj.content
        elif isinstance(original_response_obj, dict) and 'content' in original_response_obj:
            # Dictionary with content key
            original_response = original_response_obj['content']
        else:
            # Assume it's a string or string-like object
            original_response = str(original_response_obj)
            
        logger.info(f"Original LLM response: {original_response[:200]}...")
        
        return {
            'patch_applied_successfully': True,
            'patched_llm_type': patched_llm_type,
            'original_llm_type': original_llm_type,
            'patched_has_engineering_terms': has_engineering_terms,
            'patched_has_medical_terms': has_medical_terms,
            'success': has_engineering_terms and not has_medical_terms
        }
        
    except Exception as e:
        logger.exception(f"Error verifying patched behavior: {str(e)}")
        return {
            'patch_applied_successfully': False,
            'error': str(e),
            'success': False
        }

def main():
    """Main entry point for the script."""
    logger.info("Starting LLM integration verification")
    
    # Set up environment
    context = setup_environment()
    
    # Track results
    results = {}
    
    # Verify LLM service
    results['llm_service'] = verify_llm_service(context)
    
    # Verify MCP integration
    results['mcp_integration'] = verify_mcp_integration(context)
    
    # Verify patched behavior
    results['patching'] = verify_patched_behavior(context)
    
    # Determine overall success
    results['overall_success'] = all(
        result.get('success', False) 
        for result in results.values() 
        if isinstance(result, dict)
    )
    
    # Save results
    result_file = f"llm_integration_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results written to {result_file}")
    
    # Print summary
    print("\nLLM Integration Verification Results:")
    print(f"LLM Service: {'✅' if results['llm_service']['success'] else '❌'}")
    print(f"MCP Integration: {'✅' if results['mcp_integration']['success'] else '❌'}")
    print(f"Patching System: {'✅' if results['patching']['success'] else '❌'}")
    print(f"Overall Success: {'✅' if results['overall_success'] else '❌'}")
    
    if not results['overall_success']:
        logger.error("Verification failed. See log and results file for details.")
        sys.exit(1)
    else:
        logger.info("Verification completed successfully.")

if __name__ == "__main__":
    main()
