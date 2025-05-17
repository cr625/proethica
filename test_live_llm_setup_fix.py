#!/usr/bin/env python3
"""
Test Live LLM Integration Setup - Fixed Version

This script tests whether the environment is properly configured for live LLM
integration, including checking environment variables, API keys, and making 
a simple concept extraction test call.

Fixed to work with the updated Anthropic API parameters.
"""

import os
import sys
import json
import logging
import requests
import argparse
from pathlib import Path
import subprocess
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_colored(text, color):
    """Print text in color."""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'reset': '\033[0m'
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")

def check_environment_variables():
    """Check if environment variables are correctly set for live LLM."""
    print_colored("\n====== ENVIRONMENT VARIABLES CHECK ======", "blue")
    mock_setting = os.environ.get("USE_MOCK_GUIDELINE_RESPONSES", "not_set")
    print(f"USE_MOCK_GUIDELINE_RESPONSES = {mock_setting}")
    
    if mock_setting.lower() == "false":
        print_colored("✅ USE_MOCK_GUIDELINE_RESPONSES is correctly set to 'false'", "green")
    else:
        print_colored("❌ USE_MOCK_GUIDELINE_RESPONSES should be 'false' for live LLM usage", "red")
        
    # Check API keys
    print_colored("\n====== API KEY CHECK ======", "blue")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        print_colored(f"✅ ANTHROPIC_API_KEY is set (length: {len(anthropic_key)})", "green")
    else:
        print_colored("❌ ANTHROPIC_API_KEY is not set - live LLM calls will fail", "red")
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        print_colored(f"✅ OPENAI_API_KEY is set (length: {len(openai_key)})", "green")
    else:
        print_colored("⚠️ OPENAI_API_KEY is not set - not required but helpful for embeddings", "yellow")
    
    return mock_setting.lower() == "false" and bool(anthropic_key)

def test_mcp_server(port=5001):
    """Test if the MCP server is running and check its configuration."""
    print_colored("\n====== MCP SERVER CHECK ======", "blue")
    try:
        # Check server health
        health_url = f"http://localhost:{port}/health"
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print_colored(f"✅ MCP server is running on port {port}", "green")
            print(f"   Response: {response.json()}")
        else:
            print_colored(f"❌ MCP server health check failed: {response.status_code}", "red")
            return False
    except requests.RequestException as e:
        print_colored(f"❌ MCP server connection failed: {str(e)}", "red")
        print_colored(f"   Is the server running on port {port}?", "yellow")
        return False
    
    return True

def extract_concepts_test(port=5001, timeout=60):
    """Test the concept extraction with a small sample and verify if it uses LLM."""
    print_colored("\n====== CONCEPT EXTRACTION TEST ======", "blue")
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
            print_colored("⚠️ Very fast response time (< 1 sec) suggests MOCK MODE is still active", "yellow")
        elif elapsed_time > 5.0:
            print_colored("✅ Response time suggests REAL LLM processing (took significant time)", "green")
        
        # Check response status
        if response.status_code == 200:
            result = response.json()
            
            # Save response for analysis
            with open("concept_extraction_test_result.json", "w") as f:
                json.dump(result, f, indent=2)
            print("\nFull response saved to 'concept_extraction_test_result.json' for analysis")
            
            # Extract the concepts
            if "result" in result and "concepts" in result["result"]:
                concepts = result["result"]["concepts"]
                print(f"\nExtracted {len(concepts)} concepts from test text:")
                
                # Check if response has any mock indicators
                is_mock = False
                if "result" in result and "mock" in result["result"]:
                    is_mock = result["result"]["mock"]
                    if is_mock:
                        print_colored("❌ Response contains 'mock: true' - Mock mode is still active!", "red")
                    else:
                        print_colored("✅ Response contains 'mock: false' - Using real LLM!", "green")
                
                if concepts:
                    # Print first few concepts
                    for i, concept in enumerate(concepts[:3]):
                        print(f"  {i+1}. {concept.get('label', 'No Label')}: {concept.get('description', 'No Description')[:50]}...")
                    
                    # Look for indicators of real LLM vs mock in the response
                    has_detailed_descriptions = any(len(c.get("description", "")) > 100 for c in concepts)
                    has_varied_confidence = len(set(c.get("confidence", 0) for c in concepts if "confidence" in c)) > 2
                    
                    if has_detailed_descriptions and has_varied_confidence:
                        print_colored("\n✅ Concepts have detailed descriptions and varied confidence scores - likely REAL LLM response", "green")
                    else:
                        print_colored("\n⚠️ Concepts have simple descriptions or uniform confidence - might be MOCK data", "yellow")
                else:
                    print_colored("\n❌ No concepts were extracted", "red")
                    
                # Check debug info for elapsed time
                if "debug" in result["result"] and "elapsed_time" in result["result"]["debug"]:
                    api_time = result["result"]["debug"]["elapsed_time"]
                    if api_time > 5.0:
                        print_colored(f"✅ API reports elapsed_time of {api_time:.2f} seconds - confirms real LLM use", "green")
                    else:
                        print_colored(f"⚠️ API reports elapsed_time of {api_time:.2f} seconds - suspiciously fast", "yellow")
            
                # Return concept extraction success, elapsed time, and whether it's using mock data
                return True, elapsed_time, is_mock
                
            elif "error" in result["result"]:
                print_colored(f"❌ Error in concept extraction: {result['result']['error']}", "red")
                return False, elapsed_time, False
            else:
                print_colored(f"❌ Response did not contain concepts or error message: {result}", "red")
                return False, elapsed_time, False
            
        else:
            print_colored(f"❌ Concept extraction failed with status code: {response.status_code}", "red")
            try:
                print(f"Response content: {response.text}")
            except Exception as e:
                print(f"Could not print response content: {e}")
            return False, elapsed_time, False
    except requests.RequestException as e:
        print_colored(f"❌ Concept extraction request failed: {str(e)}", "red")
        return False, 0, False

def test_llm_connection():
    """Directly test connection to the Anthropic Claude API."""
    print_colored("\n====== DIRECT LLM CONNECTION TEST ======", "blue")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not anthropic_key:
        print_colored("❌ Cannot test LLM connection - ANTHROPIC_API_KEY not set", "red")
        return False
    
    try:
        from anthropic import Anthropic
        print_colored("✅ anthropic library is installed", "green")
    except ImportError:
        print_colored("❌ anthropic library is not installed - please install it with: pip install anthropic", "red")
        return False
    
    try:
        anthropic_client = Anthropic(api_key=anthropic_key)
        print_colored("✅ Created Anthropic client object", "green")
        
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
            print_colored(f"✅ Received response from Claude API in {elapsed_time:.2f} seconds:", "green")
            print(f"   Response content: \"{content[:100]}...\"")
            return True
        else:
            print_colored(f"⚠️ Got API response but content was empty or unexpected format", "yellow")
            return False
            
    except Exception as e:
        print_colored(f"❌ Anthropic API test failed: {str(e)}", "red")
        print_colored("   This suggests the API key may be invalid or there's a network/authentication issue", "red")
        return False

def run_mcp_server_with_live_llm(port=5001):
    """Attempt to start the MCP server with live LLM mode forcibly enabled."""
    print_colored("\n====== LAUNCHING MCP SERVER WITH LIVE LLM ======", "blue")
    
    # Force environment variable to false
    os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "false"
    print("Set USE_MOCK_GUIDELINE_RESPONSES=false in current environment")
    
    # Check if the server is already running
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        if response.status_code == 200:
            print_colored(f"MCP server already running on port {port}. Please stop it first.", "yellow")
            return False
    except requests.RequestException:
        # This is expected if the server isn't running
        pass
    
    # Import modules needed for running the server
    try:
        # Check if we can find the server module
        mcp_server_path = Path("mcp/run_enhanced_mcp_server_with_guidelines.py")
        if not mcp_server_path.exists():
            print_colored(f"❌ Could not find MCP server module at {mcp_server_path}", "red")
            return False
            
        print(f"Found MCP server module at {mcp_server_path}")
        print_colored("Starting MCP server with live LLM mode...", "blue")
        
        # Prepare command to run in a separate process
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
                print_colored(f"✅ MCP server successfully started on port {port}", "green")
                return True
            else:
                print_colored(f"⚠️ MCP server responded with unexpected status: {response.status_code}", "yellow")
                return False
        except requests.RequestException as e:
            print_colored(f"❌ MCP server did not respond to health check: {str(e)}", "red")
            return False
            
    except Exception as e:
        print_colored(f"❌ Error starting MCP server: {str(e)}", "red")
        return False

def manual_verification_instructions():
    """Provide instructions for manual verification."""
    print_colored("\n====== MANUAL VERIFICATION INSTRUCTIONS ======", "blue")
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
    print_colored("Forcibly set USE_MOCK_GUIDELINE_RESPONSES=false", "green")
    
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
    
    print_colored("=" * 80, "blue")
    print_colored("LIVE LLM INTEGRATION TEST", "blue")
    print_colored("=" * 80, "blue")
    
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
    print_colored("\n" + "=" * 80, "blue")
    print_colored("TEST SUMMARY", "blue")
    print_colored("=" * 80, "blue")
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
    print_colored("\n" + "=" * 80, "blue")
    if env_ok and llm_ok and server_ok and concept_ok and not is_mock:
        print_colored("RESULT: ✅ LIVE LLM INTEGRATION IS WORKING CORRECTLY", "green")
    else:
        print_colored("RESULT: ❌ LIVE LLM INTEGRATION IS NOT WORKING CORRECTLY", "red")
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
