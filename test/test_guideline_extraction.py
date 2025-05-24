#!/usr/bin/env python3
"""
Test script for guideline concept extraction with fixed Anthropic SDK.
"""

import os
import sys
import json
from pathlib import Path
from flask import Flask

# Set up paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("===============================================")
print("Testing Guideline Concept Extraction")
print("===============================================")

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env")
except ImportError:
    print("⚠️ python-dotenv not installed, skipping .env loading")
    
# Check for API key
api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    print("❌ ANTHROPIC_API_KEY not found in environment variables")
    print("Make sure to add your API key to the .env file")
    sys.exit(1)
else:
    print("✅ Found ANTHROPIC_API_KEY in environment variables")

# Create a sample guideline for testing
sample_guideline = """
# Engineering Ethics Guidelines

## Professional Responsibility
Engineers shall hold paramount the safety, health, and welfare of the public.

## Honesty and Integrity
Engineers shall be objective and truthful in professional reports, statements, or testimony.

## Confidentiality
Engineers shall not disclose confidential information without proper consent.

## Competence
Engineers shall perform services only in areas of their competence.

## Conflicts of Interest
Engineers shall avoid conflicts of interest and disclose unavoidable conflicts.
"""

try:
    # Create a minimal Flask application for testing
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['ANTHROPIC_API_KEY'] = api_key

    # Set up database URI to avoid connection attempts
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Import app and initialize
    import app as app_module
    
    # Run within application context
    with app.app_context():
        # Import the guideline analysis service
        from app.services.guideline_analysis_service import GuidelineAnalysisService
        print("✅ Successfully imported GuidelineAnalysisService")
        
        # Create service instance
        service = GuidelineAnalysisService()
        print("✅ Created GuidelineAnalysisService instance")
        
        # Mock MCP client for testing
        service.mcp_client.mcp_url = None  # Force direct LLM route
        
        # Temporarily enable mock response mode to avoid API calls in case of issues
        print("\nStep 1: Testing with mock response mode")
        os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'true'
        mock_result = service.extract_concepts(sample_guideline)
        print(f"✅ Mock extraction returned {len(mock_result.get('concepts', []))} concepts")
        
        # Print sample mock concepts
        if mock_result.get('concepts'):
            print("\nSample mock concepts:")
            for i, concept in enumerate(mock_result.get('concepts')[:3]):
                print(f"  - {concept.get('label')}: {concept.get('type')} ({concept.get('confidence')})")
        
        # Test with actual LLM
        print("\nStep 2: Testing with real Anthropic API")
        os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'false'
        
        try:
            # Try to extract concepts
            result = service.extract_concepts(sample_guideline)
            
            if 'error' in result:
                print(f"⚠️ Warning: {result.get('error')}")
                if 'concepts' in result:
                    print(f"✅ Despite error, received {len(result.get('concepts', []))} fallback concepts")
                else:
                    print("❌ No concepts returned in response")
            else:
                print(f"✅ Successfully extracted {len(result.get('concepts', []))} concepts")
                
                # Print a few sample concepts
                if result.get('concepts'):
                    print("\nSample extracted concepts:")
                    for i, concept in enumerate(result.get('concepts')[:5]):
                        print(f"  - {concept.get('label')}: {concept.get('type')} ({concept.get('confidence')})")
                
                # Save results to file for inspection
                with open('test_concepts_output.json', 'w') as f:
                    json.dump(result, f, indent=2)
                print("\n✅ Full results saved to test_concepts_output.json")
                
        except Exception as e:
            print(f"❌ Error during concept extraction: {str(e)}")
            import traceback
            traceback.print_exc()
    
except Exception as e:
    print(f"❌ Setup error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n===============================================")
print("Test complete!")
print("===============================================")
