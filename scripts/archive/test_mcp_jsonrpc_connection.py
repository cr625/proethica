#!/usr/bin/env python3
"""
Test MCP server JSON-RPC connection.

This script tests the connection to the MCP server using the JSON-RPC protocol.
It's useful for debugging connectivity issues in the GitHub Codespaces environment.
"""

import sys
import json
import requests
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Test MCP server JSON-RPC connection")
    parser.add_argument("--url", default="http://localhost:5001/jsonrpc", help="MCP server URL")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return parser.parse_args()

def test_jsonrpc_connection(url, timeout=10, verbose=False):
    """
    Test connection to MCP server using JSON-RPC.
    """
    if verbose:
        print(f"Testing connection to MCP server at {url}")
    
    # Prepare JSON-RPC request to list available tools
    request_data = {
        "jsonrpc": "2.0",
        "method": "list_tools",
        "params": {},
        "id": 1
    }
    
    try:
        # Send the request
        if verbose:
            print("Sending JSON-RPC request...")
        
        response = requests.post(
            url,
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            
            # Check if the response contains the expected fields
            if "jsonrpc" in result and "result" in result and "id" in result:
                if verbose:
                    print("MCP server responded successfully with a valid JSON-RPC response")
                    print("\nAvailable tools:")
                    
                    # Print available tools if any
                    if "tools" in result["result"]:
                        for tool in result["result"]["tools"]:
                            print(f"- {tool}")
                    else:
                        print("No tools found")
                        
                # Check specifically for the guideline analysis module tools
                guideline_tools = []
                for tool in result["result"].get("tools", []):
                    if isinstance(tool, dict) and "name" in tool:
                        if "guideline" in tool["name"].lower():
                            guideline_tools.append(tool["name"])
                    elif isinstance(tool, str):
                        if "guideline" in tool.lower():
                            guideline_tools.append(tool)
                
                if guideline_tools:
                    if verbose:
                        print("\nGuideline analysis tools found:")
                        for tool in guideline_tools:
                            print(f"- {tool}")
                    return True, "Connection successful. Guideline tools available."
                else:
                    if verbose:
                        print("\nWARNING: No guideline analysis tools found")
                    return True, "Connection successful, but no guideline tools found."
            else:
                if verbose:
                    print("Response does not follow JSON-RPC format:")
                    print(json.dumps(result, indent=2))
                return False, f"Invalid JSON-RPC response: {result}"
        else:
            if verbose:
                print(f"Request failed with status code {response.status_code}")
                print(f"Response: {response.text}")
            return False, f"Failed with status {response.status_code}: {response.text}"
    
    except requests.exceptions.ConnectionError:
        error_msg = f"Connection error: Could not connect to {url}"
        if verbose:
            print(error_msg)
            print("Make sure the MCP server is running")
        return False, error_msg
    
    except requests.exceptions.Timeout:
        error_msg = f"Connection timeout after {timeout} seconds"
        if verbose:
            print(error_msg)
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if verbose:
            print(error_msg)
        return False, error_msg

def main():
    args = parse_args()
    success, message = test_jsonrpc_connection(args.url, args.timeout, args.verbose)
    
    if success:
        print(f"✅ SUCCESS: {message}")
        return 0
    else:
        print(f"❌ ERROR: {message}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
