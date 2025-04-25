#!/usr/bin/env python3
"""
Utility script to verify and test the ontology visualization system.

This script:
1. Verifies the server is running
2. Tests critical API endpoints for the visualization
3. Optionally outputs visualization HTML to a file for viewing

Usage:
    python check_ontology_visualization.py [ontology_id] [output_file]

Arguments:
    ontology_id: ID of the ontology to check (default: 1)
    output_file: Path to save HTML output (default: None - don't save)

Example:
    python check_ontology_visualization.py 1 visualization.html
"""

import sys
import os
import json
import requests
import time
from urllib.parse import urljoin

# Configuration
SERVER_URL = "http://localhost:3333"
VISUALIZATION_PATH = "/ontology-editor/visualize/"
API_BASE = "/ontology-editor/api/"

def green(text):
    """Format text in green color."""
    return f"\033[92m{text}\033[0m"

def red(text):
    """Format text in red color."""
    return f"\033[91m{text}\033[0m"

def yellow(text):
    """Format text in yellow color."""
    return f"\033[93m{text}\033[0m"

def check_server():
    """Check if the server is running."""
    try:
        response = requests.get(SERVER_URL, timeout=5)
        if response.status_code == 200:
            print(green("✓ Server is running"))
            return True
        else:
            print(red(f"✗ Server returned unexpected status code: {response.status_code}"))
            return False
    except requests.ConnectionError:
        print(red("✗ Could not connect to server. Make sure it's running."))
        print(yellow("  Hint: Run ./start_proethica.sh to start the server"))
        return False
    except Exception as e:
        print(red(f"✗ Error connecting to server: {str(e)}"))
        return False

def check_api_endpoints(ontology_id):
    """Check various API endpoints required for visualization."""
    endpoints = [
        # Try both singular and plural versions since there might be inconsistency
        (f"{API_BASE}ontologies", "List of ontologies"),
        (f"{API_BASE}ontology/{ontology_id}", "Single ontology details"),
        (f"{API_BASE}ontologies/{ontology_id}", "Single ontology details (alternative)"),
        (f"{API_BASE}ontology/{ontology_id}/hierarchy", "Ontology hierarchy"),
        (f"{API_BASE}ontology/{ontology_id}/entities", "Ontology entities"),
    ]
    
    results = []
    for endpoint, description in endpoints:
        try:
            url = urljoin(SERVER_URL, endpoint)
            print(f"Testing: {url} ({description})")
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(green(f"  ✓ Success ({response.status_code})"))
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        print(f"  Keys: {', '.join(data.keys())}")
                    results.append((endpoint, True, data))
                except:
                    print(yellow("  ⚠ Response is not valid JSON"))
                    results.append((endpoint, True, response.text[:100] + "..."))
            else:
                print(red(f"  ✗ Failed ({response.status_code})"))
                results.append((endpoint, False, response.status_code))
        except Exception as e:
            print(red(f"  ✗ Error: {str(e)}"))
            results.append((endpoint, False, str(e)))
    
    return results

def check_visualization(ontology_id, output_file=None):
    """Check the visualization endpoint and optionally save HTML."""
    vis_url = urljoin(SERVER_URL, f"{VISUALIZATION_PATH}{ontology_id}")
    
    try:
        print(f"Fetching visualization from: {vis_url}")
        response = requests.get(vis_url, timeout=10)
        
        if response.status_code == 200:
            print(green(f"✓ Successfully retrieved visualization HTML ({len(response.text)} bytes)"))
            
            # Check for key visualization elements
            checks = [
                ("D3.js Library", "d3.v7.min.js" in response.text),
                ("Visualization Container", "visualization-svg-container" in response.text),
                ("Hierarchical View Button", "hierarchical-view-btn" in response.text),
                ("Entity Type Filters", "filter-btn" in response.text),
                ("Tooltip Functionality", "showTooltip" in response.text),
            ]
            
            for name, result in checks:
                if result:
                    print(green(f"  ✓ {name} found"))
                else:
                    print(red(f"  ✗ {name} not found"))
            
            # Save to file if requested
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(green(f"✓ Visualization saved to {output_file}"))
                print(yellow(f"  Open this file in a web browser to view the visualization"))
            
            return True
        else:
            print(red(f"✗ Failed to get visualization ({response.status_code})"))
            return False
    except Exception as e:
        print(red(f"✗ Error getting visualization: {str(e)}"))
        return False

def main():
    """Main entry point."""
    ontology_id = 1  # Default
    output_file = None
    
    # Process arguments
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(red(f"Invalid ontology_id: {sys.argv[1]}. Using default: 1"))
            ontology_id = 1
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print(f"Checking ontology visualization for ID: {ontology_id}")
    print("-" * 50)
    
    # Check if server is running
    if not check_server():
        return 1
    
    print("\nChecking API endpoints:")
    print("-" * 50)
    api_results = check_api_endpoints(ontology_id)
    
    print("\nChecking visualization:")
    print("-" * 50)
    check_visualization(ontology_id, output_file)
    
    print("\nSummary:")
    print("-" * 50)
    working_endpoints = sum(1 for _, success, _ in api_results if success)
    print(f"API Endpoints: {working_endpoints}/{len(api_results)} working")
    
    # Provide some guidance
    print("\nNext steps:")
    if working_endpoints < len(api_results):
        print(yellow("- Some API endpoints are not working. Check the route definitions in ontology_editor/api/routes.py"))
    
    if output_file:
        print(yellow(f"- View the saved visualization by opening {output_file} in a web browser"))
    else:
        print(yellow("- Run this script with an output file parameter to save the visualization HTML"))
    
    print(yellow("- Continue developing the visualization by enhancing ontology_editor/templates/visualize.html"))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
