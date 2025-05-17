#!/usr/bin/env python3
"""
Test Live LLM Integration Setup

This script tests whether the environment is properly configured for live LLM
integration, including checking environment variables, API keys, and making 
a simple concept extraction test call.
"""

import os
import sys
import json
import logging
import requests
import argparse
from pathlib import Path
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment_variables():
    """Check if environment variables are correctly set for live LLM."""
    print("\n====== ENVIRONMENT VARIABLES CHECK ======")
    mock_setting = os.environ.get("USE_MOCK_GUIDELINE_RESPONSES", "not_set")
    print(f"USE_MOCK_GUIDELINE_RESPONSES = {mock_setting}")
    
    if mock_setting.lower() == "false":
        print("✅ USE_MOCK_GUIDELINE_RESPONSES is correctly set to 'false'")
    else:
        print("❌ USE_MOCK_GUIDELINE_RESPONSES should be 'false' for live LLM usage")
        
    # Check API keys
    print("\n====== API KEY CHECK ======")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        print(f"✅ ANTHROPIC_API_KEY is set (length: {len(anthropic_key)})")
    else:
        print("❌ ANTHROPIC_API_KEY is not set - live LLM calls will fail")
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        print(f"✅ OPENAI_API_KEY is set (length: {len(openai_key)})")
    else:
        print("⚠️ OPENAI_API_KEY is not set - not required but helpful for embeddings")
    
    return mock_setting.lower() == "false" and bool(anthropic_key)

def test_mcp_server(port=5001):
    """Test if the MCP server is running and check its configuration."""
    print("\n====== MCP SERVER CHECK ======")
    try:
        # Check server health
        health_url = f"http://localhost:{port}/health"
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ MCP server is running on port {port}")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ MCP server health check failed: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ MCP server connection failed: {str(e)}")
        print(f"   Is the server running on port {port}?")
        return False
    
    return True

def extract_concepts_test(port=5001, timeout=60):
    """Test the concept extraction with a small sample and verify if it uses LLM."""
    print("\n====== CONCEPT EXTRACTION TEST ======")
    print("Making a test call to extract concepts - this will help determine if LLM is being used...")
    
    # Small test guideline text
    test_text = """
    Engineering Ethics Guideline
    
    Engineers shall hold paramount the safety, health, and welfare of the public.
    Engineers shall perform services only in areas of their competence.
    Engineers shall act as faithful agents or trustees for each client or employer.
    """
    
    # Prepare the request
    print("Preparing test request...")
    request_data = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "extract_guideline_concepts",
            "arguments": {
                "content": test_text,
                "ontology_source": "engineering-ethics"
            }
        },
        "id": 1
    }
    
    # Time the request for live LLM detection
    start_time = time.time()
    print(f"Starting concept extraction request at: {start_time}")
    
    try:
        # Make the request with a longer timeout
        response = requests.post(
            f"http://localhost:{port}/jsonrpc",
            json=request_data,
            timeout=timeout  # Longer timeout for potential LLM call
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        print(f"Request completed in {elapsed_time:.2f} seconds")
        
        # Interpret response time
        if elapsed_time < 1.0:
            print("⚠️ Very fast response time (< 1 sec) suggests MOCK MODE is still active")
        elif elapsed_time > 5.0 and elapsed_time < 60.0:
            print("✅ Response time suggests REAL LLM processing (took significant time)")
        
        # Check response status
        if response.status_code == 200:
            result = response.json()
            
            # Extract the concepts
            if "result" in result and "concepts" in result["result"]:
                concepts = result["result"]["concepts"]
                print(f"\nExtracted {len(concepts)} concepts from test text:")
                
                # Check if response has any mock indicators
                if "mock" in result["result"] and result["result"]["mock"]:
                    print("❌ Response contains 'mock: true' - Mock mode is still active!")
                else:
                    # Print first few concepts
                    for i, concept in enumerate(concepts[:3]):
                        print(f"  {i+1}. {concept.get('label', 'No Label')}: {concept.get('description', 'No Description')[:50]}...")
                    
                    # Look for indicators of real LLM vs mock in the response
                    has_detailed_descriptions = any(len(c.get("description", "")) > 100 for c in concepts)
                    has_varied_confidence = len(set(c.get("confidence", 0) for c in concepts)) > 2
                    
                    if has_detailed_descriptions and has_varied_confidence:
                        print("\n✅ Concepts have detailed descriptions and varied confidence scores - likely REAL LLM response")
                    else:
                        print("\n⚠️ Concepts have simple descriptions or uniform confidence - might be MOCK data")
                
                # Save response for analysis
                with open("concept_extraction_test_result.json", "w") as f:
                    json.dump(result, f, indent=2)
                print("\nFull response saved to 'concept_extraction_test_result.json' for analysis")
                
            else:
                print(f"❌ Response did not contain concepts: {result}")
            
            return True, elapsed_time, "mock" in result.get("result", {})
            
        else:
            print(f"❌ Concept extraction failed with status code: {response.status_code}")
            return False, elapsed_time, False
            
    except requests.RequestException as e:
        print(f"❌ Concept extraction request failed: {str(e)}")
        return False, 0, False

def test_llm_connection():
    """Directly test connection to the Anthropic Claude API."""
    print("\n====== DIRECT LLM CONNECTION TEST ======")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not anthropic_key:
        print("❌ Cannot test LLM connection - ANTHROPIC_API_KEY not set")
        return False
    
    try:
        from anthropic import Anthropic
        print("✅ anthropic library is installed")
    except ImportError:
        print("❌ anthropic library is not installed - please install it with: pip install anthropic")
        return False
    
    try:
        anthropic_client = Anthropic(api_key=anthropic_key)
        print("✅ Created Anthropic client object")
        
        # Make a simple API call
        print("Testing API connection with small request...")
        start_time = time.time()
        
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello! This is a test message to check API connectivity. Please respond with 'API connection successful'."}
            ]
        )
        
        elapsed_time = time.time() - start_time
        
        # Check response
        if response and hasattr(response, 'content') and response.content:
            content = response.content[0].text
            print(f"✅ Received response from Claude API in {elapsed_time:.2f} seconds:")
            print(f"   Response content: \"{content[:100]}...\"")
            return True
        else:
            print(f"⚠️ Got API response but content was empty or unexpected format")
            return False
            
    except Exception as e:
        print(f"❌ Anthropic API test failed: {str(e)}")
        print("   This suggests the API key may be invalid or there's a network/authentication issue")
        return False

def run_mcp_server_with_live_llm(port=5001):
    """Attempt to start the MCP server with live LLM mode forcibly enabled."""
    print("\n====== LAUNCHING MCP SERVER WITH LIVE LLM ======")
    
    # Force environment variable to false
    os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "false"
    print("Set USE_MOCK_GUIDELINE_RESPONSES=false in current environment")
    
    # Check if the server is already running
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        if response.status_code == 200:
            print(f"MCP server already running on port {port}. Please stop it first.")
            return False
    except requests.RequestException:
        # This is expected if the server isn't running
        pass
    
    # Import modules needed for running the server
    try:
        # Check if we can find the server module
        mcp_server_path = Path("mcp/run_enhanced_mcp_server_with_guidelines.py")
        if not mcp_server_path.exists():
            print(f"❌ Could not find MCP server module at {mcp_server_path}")
            return False
            
        print(f"Found MCP server module at {mcp_server_path}")
        print("Starting MCP server with live LLM mode...")
        
        # Prepare command to run in a separate process
        import subprocess
        cmd = f"python {mcp_server_path} --port {port}"
        
        # Start the server in a new process
        process = subprocess.Popen(
            cmd, 
            shell=True,
            env={**os.environ, "USE_MOCK_GUIDELINE_RESPONSES": "false"}
        )
        
        print(f"MCP server process started with PID: {process.pid}")
        print("Waiting 5 seconds for server to initialize...")
        time.sleep(5)
        
        # Check if server is running
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                print(f"✅ MCP server successfully started on port {port}")
                return True
            else:
                print(f"⚠️ MCP server responded with unexpected status: {response.status_code}")
                return False
        except requests.RequestException as e:
            print(f"❌ MCP server did not respond to health check: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting MCP server: {str(e)}")
        return False

def manual_verification_instructions():
    """Provide instructions for manual verification."""
    print("\n====== MANUAL VERIFICATION INSTRUCTIONS ======")
    print("To further verify live LLM integration is working:")
    print("1. Start the UI application with: ./run_with_live_llm.sh")
    print("2. When prompted, select option 1 to start the MCP server first")
    print("3. Wait for the application to fully start")
    print("4. Open a browser and navigate to: http://localhost:3333")
    print("5. Create or select a world and upload a guideline")
    print("6. Click 'Extract Concepts' and observe the following:")
    print("   - The request should take 30-45 seconds (indicating real LLM processing)")
    print("   - The terminal should show logs about calling the LLM API")
    print("   - The extracted concepts should be detailed and varied")
    print("\nIf the request completes instantly (<1 second), mock mode is still active")

def force_env_variables():
    """Forcibly set environment variables for testing."""
    os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "false"
    print("Forcibly set USE_MOCK_GUIDELINE_RESPONSES=false")
    
    # Output current environment variables
    print("\nCurrent environment variables:")
    print(f"USE_MOCK_GUIDELINE_RESPONSES: {os.environ.get('USE_MOCK_GUIDELINE_RESPONSES', 'not set')}")
    print(f"ANTHROPIC_API_KEY: {'*****' if os.environ.get('ANTHROPIC_API_KEY') else 'not set'}")
    print(f"OPENAI_API_KEY: {'*****' if os.environ.get('OPENAI_API_KEY') else 'not set'}")
    
    return True

def main():
    """Run the diagnostics and tests."""
    parser = argparse.ArgumentParser(description="Test Live LLM Integration Setup")
    parser.add_argument("--port", type=int, default=5001, help="MCP server port (default: 5001)")
    parser.add_argument("--start-server", action="store_true", help="Attempt to start the MCP server")
    parser.add_argument("--force-env", action="store_true", help="Force environment variables to correct values")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout for concept extraction test in seconds")
    args = parser.parse_args()
    
    print("=" * 80)
    print("LIVE LLM INTEGRATION TEST")
    print("=" * 80)
    
    # Force environment variables if requested
    if args.force_env:
        force_env_variables()
    
    # Check environment variables
    env_ok = check_environment_variables()
    
    # Test LLM connection
    llm_ok = test_llm_connection()
    
    # Start server if requested
    server_started = False
    if args.start_server:
        server_started = run_mcp_server_with_live_llm(args.port)
    
    # Test MCP server if not starting one
    if not args.start_server:
        server_ok = test_mcp_server(args.port)
    else:
        server_ok = server_started
    
    # Only run concept extraction test if server is available
    concept_ok = False
    is_mock = True
    if server_ok:
        concept_ok, elapsed_time, is_mock = extract_concepts_test(args.port, args.timeout)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Environment variables: {'✅ OK' if env_ok else '❌ NOT OK'}")
    print(f"Direct LLM connection: {'✅ OK' if llm_ok else '❌ NOT OK'}")
    print(f"MCP server: {'✅ OK' if server_ok else '❌ NOT OK'}")
    
    if concept_ok:
        if is_mock:
            print(f"Concept extraction: ❌ Using MOCK DATA despite environment settings")
        else:
            print(f"Concept extraction: ✅ Using REAL LLM")
    else:
        print(f"Concept extraction: ❌ Test failed")
    
    # Print overall result
    print("\n" + "=" * 80)
    if env_ok and llm_ok and server_ok and concept_ok and not is_mock:
        print("RESULT: ✅ LIVE LLM INTEGRATION IS WORKING CORRECTLY")
    else:
        print("RESULT: ❌ LIVE LLM INTEGRATION IS NOT WORKING CORRECTLY")
        print("\nPossible issues:")
        if not env_ok:
            print("- Environment variables not correctly set")
        if not llm_ok:
            print("- LLM API connection issues (check API key)")
        if not server_ok:
            print("- MCP server not running or not responding")
        if not concept_ok:
            print("- Concept extraction failed")
        if is_mock:
            print("- Mock mode still active in MCP server despite environment settings")
    
    # Provide manual verification instructions
    manual_verification_instructions()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
