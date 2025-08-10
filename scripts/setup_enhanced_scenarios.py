#!/usr/bin/env python3
"""Setup script for Enhanced Scenario Generation features.

This script helps configure and test the enhanced LLM-driven scenario generation
system, including feature validation and environment setup.
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from config.enhanced_scenario_config import EnhancedScenarioConfig, generate_env_template, ENVIRONMENT_VARIABLES
except ImportError:
    print("Error: Could not import enhanced scenario configuration")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

def validate_configuration():
    """Validate current configuration and report status."""
    print("🔍 Validating Enhanced Scenario Generation Configuration...")
    print("=" * 60)
    
    validation = EnhancedScenarioConfig.validate_configuration()
    
    print(f"Configuration Status: {'✅ VALID' if validation['valid'] else '❌ INVALID'}")
    print()
    
    # Show current settings
    config = validation['config']
    print("📋 Current Configuration:")
    print(f"  Enhanced Generation: {'✅' if config['features']['enhanced_generation'] else '❌'}")
    print(f"  MCP Integration: {'✅' if config['features']['mcp_integration'] else '❌'}")
    print(f"  LLM Refinement: {'✅' if config['features']['llm_refinement'] else '❌'}")
    print(f"  LLM Provider: {config['llm']['provider']}")
    print(f"  MCP Server: {config['mcp']['server_url']}")
    print()
    
    # Show errors
    if validation['errors']:
        print("❌ Configuration Errors:")
        for error in validation['errors']:
            print(f"  • {error}")
        print()
    
    # Show warnings
    if validation['warnings']:
        print("⚠️  Configuration Warnings:")
        for warning in validation['warnings']:
            print(f"  • {warning}")
        print()
    
    return validation['valid']

def enable_enhanced_generation():
    """Enable enhanced generation and show setup instructions."""
    print("🚀 Enabling Enhanced Scenario Generation...")
    print("=" * 60)
    
    # Check current status
    current_status = os.environ.get('ENHANCED_SCENARIO_GENERATION', 'false').lower()
    
    if current_status == 'true':
        print("✅ Enhanced generation is already enabled in current environment")
    else:
        print("❌ Enhanced generation is not enabled in current environment")
        print()
        print("To enable enhanced generation, set the following environment variable:")
        print("export ENHANCED_SCENARIO_GENERATION=true")
        print()
    
    print("📋 Required Setup Steps:")
    print("1. Set ENHANCED_SCENARIO_GENERATION=true")
    print("2. Configure API key for your chosen LLM provider:")
    print("   • For Anthropic: export ANTHROPIC_API_KEY=your_key_here")
    print("   • For OpenAI: export OPENAI_API_KEY=your_key_here")
    print("3. Ensure MCP server is running at http://localhost:5001")
    print("4. Test with: python scripts/setup_enhanced_scenarios.py --test")
    print()
    
    # Show environment template
    print("📄 Environment Variable Template:")
    print("-" * 40)
    print(generate_env_template())

def test_components():
    """Test enhanced scenario generation components."""
    print("🧪 Testing Enhanced Scenario Generation Components...")
    print("=" * 60)
    
    # Test 1: Configuration validation
    print("1. Configuration Validation:")
    config_valid = validate_configuration()
    print(f"   Result: {'✅ PASS' if config_valid else '❌ FAIL'}")
    print()
    
    if not config_valid:
        print("Cannot proceed with component testing - fix configuration first")
        return False
    
    # Test 2: Import enhanced services
    print("2. Enhanced Service Import:")
    try:
        from app.services.scenario_pipeline.enhanced_llm_scenario_service import EnhancedLLMScenarioService
        print("   Enhanced LLM Service: ✅ PASS")
    except ImportError as e:
        print(f"   Enhanced LLM Service: ❌ FAIL - {e}")
        return False
    
    try:
        from app.services.scenario_pipeline.mcp_ontology_client import MCPOntologyClient
        print("   MCP Ontology Client: ✅ PASS")
    except ImportError as e:
        print(f"   MCP Ontology Client: ❌ FAIL - {e}")
        return False
    
    print()
    
    # Test 3: LLM Service availability
    print("3. LLM Service Availability:")
    try:
        from app.services.langchain_claude import LangChainClaudeService
        llm_service = LangChainClaudeService.get_instance()
        print("   LangChain Claude Service: ✅ PASS")
    except Exception as e:
        print(f"   LangChain Claude Service: ❌ FAIL - {e}")
        return False
    
    print()
    
    # Test 4: MCP Server connectivity (if enabled)
    if EnhancedScenarioConfig.is_mcp_integration_enabled():
        print("4. MCP Server Connectivity:")
        mcp_config = EnhancedScenarioConfig.get_mcp_config()
        
        try:
            import aiohttp
            import asyncio
            
            async def test_mcp_server():
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"{mcp_config['server_url']}/health") as response:
                        return response.status == 200
            
            mcp_available = asyncio.run(test_mcp_server())
            print(f"   MCP Server ({mcp_config['server_url']}): {'✅ PASS' if mcp_available else '⚠️ UNAVAILABLE'}")
            
            if not mcp_available and not mcp_config['fallback_enabled']:
                print("   ❌ WARNING: MCP server unavailable and fallback disabled")
                
        except Exception as e:
            print(f"   MCP Server: ❌ FAIL - {e}")
            if not mcp_config['fallback_enabled']:
                return False
    else:
        print("4. MCP Server Connectivity: ⏭️ SKIPPED (integration disabled)")
    
    print()
    print("🎉 Component testing completed successfully!")
    return True

def show_usage_examples():
    """Show usage examples for enhanced scenario generation."""
    print("📚 Enhanced Scenario Generation Usage Examples")
    print("=" * 60)
    
    print("1. Basic Usage (Python):")
    print("""
from app.services.scenario_pipeline.scenario_generation_phase_a import DirectScenarioPipelineService
from app.models import Document

# Enable enhanced generation in environment
os.environ['ENHANCED_SCENARIO_GENERATION'] = 'true'

# Initialize service
pipeline = DirectScenarioPipelineService()

# Generate enhanced scenario for a case
case = Document.query.get(case_id)
scenario_data = pipeline.generate(case, overwrite=False)

print(f"Generated {scenario_data['stats']['event_count']} events")
print(f"Generated {scenario_data['stats']['decision_count']} decisions")
print(f"Pipeline version: {scenario_data['pipeline_version']}")
""")
    
    print("2. Environment Configuration:")
    print("""
# Enable all enhanced features
export ENHANCED_SCENARIO_GENERATION=true
export ANTHROPIC_API_KEY=your_anthropic_key

# Configure processing limits
export ENHANCED_SCENARIO_MAX_EVENTS=15
export ENHANCED_SCENARIO_MAX_DECISIONS=6

# Configure MCP server
export MCP_SERVER_URL=https://mcp.proethica.org
export MCP_FALLBACK_ENABLED=true
""")
    
    print("3. Testing Individual Components:")
    print("""
# Test configuration
python scripts/setup_enhanced_scenarios.py --validate

# Enable and show setup instructions  
python scripts/setup_enhanced_scenarios.py --enable

# Test all components
python scripts/setup_enhanced_scenarios.py --test
""")

def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description='Setup and test Enhanced Scenario Generation features',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--validate', 
        action='store_true',
        help='Validate current configuration'
    )
    
    parser.add_argument(
        '--enable',
        action='store_true', 
        help='Show instructions to enable enhanced generation'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test enhanced scenario generation components'
    )
    
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show usage examples'
    )
    
    parser.add_argument(
        '--env-template',
        action='store_true',
        help='Generate environment variable template'
    )
    
    args = parser.parse_args()
    
    # If no specific action, show help
    if not any([args.validate, args.enable, args.test, args.examples, args.env_template]):
        parser.print_help()
        print("\n" + "="*60)
        print("Enhanced Scenario Generation Setup Helper")
        print("="*60)
        print("Use --validate to check configuration")
        print("Use --enable to see setup instructions") 
        print("Use --test to test components")
        print("Use --examples to see usage examples")
        return
    
    success = True
    
    if args.validate:
        success = validate_configuration() and success
    
    if args.enable:
        enable_enhanced_generation()
    
    if args.test:
        success = test_components() and success
        
    if args.examples:
        show_usage_examples()
        
    if args.env_template:
        print("Environment Variable Template:")
        print("=" * 40)
        print(generate_env_template())
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()