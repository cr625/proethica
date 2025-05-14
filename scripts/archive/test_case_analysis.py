#!/usr/bin/env python3
"""
Test Case Analysis Script

This script demonstrates the basic functionality of the ontology-based
case analysis system. It will:
1. Connect to the unified ontology server
2. Extract entities from a selected ethics case
3. Analyze the case using ontological principles
4. Display the results

Usage:
    python test_case_analysis.py [case_id]
"""

import os
import sys
import json
import requests
import argparse
from pprint import pprint
import logging
from dotenv import load_dotenv
import time
from datetime import datetime
from tabulate import tabulate

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Case-Analysis-Test')

# Load environment variables
load_dotenv()

# Configuration
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
ONTOLOGY_SERVER_PORT = int(os.getenv('MCP_SERVER_PORT', '5001'))
FLASK_URL = f"http://localhost:{FLASK_PORT}"
ONTOLOGY_SERVER_URL = f"http://localhost:{ONTOLOGY_SERVER_PORT}"

def get_case_details(case_id):
    """Get details of a case from the Flask application"""
    try:
        response = requests.get(f"{FLASK_URL}/api/cases/{case_id}")
        if response.status_code != 200:
            logger.error(f"Failed to get case details: HTTP {response.status_code}")
            return None
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error getting case details: {e}")
        return None

def analyze_case_with_ontology(case_id):
    """Analyze a case using the ontology"""
    try:
        response = requests.get(f"{FLASK_URL}/api/ontology/analyze_case/{case_id}")
        if response.status_code != 200:
            logger.error(f"Failed to analyze case: HTTP {response.status_code}")
            return None
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error analyzing case: {e}")
        return None

def get_ontology_status():
    """Check the status of the ontology server"""
    try:
        response = requests.get(f"{FLASK_URL}/api/ontology/status")
        if response.status_code != 200:
            logger.error(f"Failed to get ontology status: HTTP {response.status_code}")
            return None
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error getting ontology status: {e}")
        return None

def get_case_entities(case_id):
    """Get entities extracted from a case"""
    try:
        # This endpoint would need to be implemented
        response = requests.get(f"{FLASK_URL}/api/cases/{case_id}/entities")
        if response.status_code != 200:
            logger.error(f"Failed to get case entities: HTTP {response.status_code}")
            return None
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error getting case entities: {e}")
        return None

def extract_case_entities_direct(case_text):
    """Extract entities directly from case text using ontology server"""
    try:
        response = requests.post(
            f"{ONTOLOGY_SERVER_URL}/rpc",
            json={
                'jsonrpc': '2.0',
                'method': 'case_analysis_module.extract_entities',
                'params': {
                    'text': case_text
                },
                'id': 1
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to extract entities: HTTP {response.status_code}")
            return None
            
        result = response.json()
        
        # Check for JSON-RPC error
        if 'error' in result:
            logger.error(f"RPC error: {result['error'].get('message')}")
            return None
            
        return result.get('result')
    except requests.RequestException as e:
        logger.error(f"Error extracting entities: {e}")
        return None

def list_available_cases():
    """List available cases from the Flask application"""
    try:
        response = requests.get(f"{FLASK_URL}/api/cases/list")
        if response.status_code != 200:
            logger.error(f"Failed to list cases: HTTP {response.status_code}")
            return None
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error listing cases: {e}")
        return None

def print_analysis_report(case_details, analysis_results):
    """Print a formatted report of the case analysis"""
    if not case_details or not analysis_results:
        logger.error("Missing case details or analysis results")
        return
    
    # Print case information
    print("\n" + "="*80)
    print(f"CASE ANALYSIS REPORT: {case_details.get('title', 'Unknown Case')}")
    print("="*80)
    
    print(f"\nCase ID: {case_details.get('id')}")
    print(f"Source: {case_details.get('source', 'Unknown')}")
    print(f"Date: {case_details.get('date', 'Unknown')}")
    print("\n" + "-"*80)
    
    # Print extracted entities
    entities = analysis_results.get('analysis', {}).get('entities', [])
    if entities:
        print("\nEXTRACTED ENTITIES:")
        
        # Organize entities by type
        entities_by_type = {}
        for entity in entities:
            entity_type = entity.get('type', 'Unknown')
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        # Print each type of entity
        for entity_type, type_entities in entities_by_type.items():
            print(f"\n{entity_type.upper()}:")
            
            # Prepare data for tabulate
            table_data = []
            for entity in type_entities:
                table_data.append([
                    entity.get('id', 'Unknown'),
                    entity.get('label', 'Unknown'),
                    f"{entity.get('relevance_score', 0):.2f}"
                ])
            
            print(tabulate(
                table_data,
                headers=["ID", "Label", "Relevance"],
                tablefmt="grid"
            ))
    else:
        print("\nNo entities extracted.")
    
    # Print principles
    principles = analysis_results.get('analysis', {}).get('principles', [])
    if principles:
        print("\nIDENTIFIED ETHICAL PRINCIPLES:")
        
        # Prepare data for tabulate
        table_data = []
        for principle in principles:
            status = "Unknown"
            if principle.get('is_violated'):
                status = "Violated"
            elif principle.get('is_satisfied'):
                status = "Satisfied"
            elif principle.get('is_overridden'):
                status = "Overridden"
                
            table_data.append([
                principle.get('label', 'Unknown'),
                status,
                f"{principle.get('relevance_score', 0):.2f}",
                principle.get('principle_text', '')[:50] + ('...' if len(principle.get('principle_text', '')) > 50 else '')
            ])
        
        print(tabulate(
            table_data,
            headers=["Principle", "Status", "Relevance", "Description"],
            tablefmt="grid"
        ))
    else:
        print("\nNo ethical principles identified.")
    
    # Print timeline if available
    timeline = analysis_results.get('analysis', {}).get('timeline', [])
    if timeline:
        print("\nCASE TIMELINE:")
        
        # Prepare data for tabulate
        table_data = []
        for event in timeline:
            table_data.append([
                event.get('temporal_order', '?'),
                event.get('element_label', 'Unknown event'),
                event.get('element_type', 'Unknown'),
                event.get('context', '')[:50] + ('...' if len(event.get('context', '')) > 50 else '')
            ])
        
        print(tabulate(
            table_data,
            headers=["Order", "Event", "Type", "Context"],
            tablefmt="grid"
        ))
    else:
        print("\nNo timeline available.")
    
    # Print analysis summary
    summary = analysis_results.get('analysis', {}).get('summary')
    if summary:
        print("\nANALYSIS SUMMARY:")
        print("-"*80)
        print(summary)
    else:
        print("\nNo analysis summary available.")
    
    print("\n" + "="*80 + "\n")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Test case analysis functionality')
    parser.add_argument('case_id', nargs='?', type=int, help='ID of the case to analyze')
    parser.add_argument('--list', action='store_true', help='List available cases')
    args = parser.parse_args()
    
    # Check ontology server status
    logger.info("Checking ontology server status...")
    status = get_ontology_status()
    if not status:
        logger.error("Failed to connect to ontology server. Please check if it's running.")
        sys.exit(1)
    
    logger.info(f"Connected to ontology server: {status.get('ontology_server')}")
    
    # List cases if requested
    if args.list:
        logger.info("Listing available cases...")
        cases = list_available_cases()
        if cases:
            print("\nAVAILABLE CASES:")
            # Prepare data for tabulate
            table_data = []
            for case in cases.get('cases', []):
                table_data.append([
                    case.get('id'),
                    case.get('title', 'Unknown')[:50] + ('...' if len(case.get('title', '')) > 50 else ''),
                    case.get('source', 'Unknown'),
                    case.get('date', 'Unknown')
                ])
            
            print(tabulate(
                table_data,
                headers=["ID", "Title", "Source", "Date"],
                tablefmt="grid"
            ))
        else:
            print("No cases available.")
        return
    
    # Check if case_id is provided
    if not args.case_id:
        logger.error("No case ID provided. Use --list to see available cases.")
        sys.exit(1)
    
    case_id = args.case_id
    
    # Get case details
    logger.info(f"Getting details for case {case_id}...")
    case_details = get_case_details(case_id)
    if not case_details:
        logger.error(f"Failed to get details for case {case_id}")
        sys.exit(1)
    
    logger.info(f"Analyzing case: {case_details.get('title')}")
    
    # Analyze the case
    logger.info("Performing ontology-based analysis...")
    analysis_results = analyze_case_with_ontology(case_id)
    
    # If the API endpoint isn't implemented yet, simulate some results
    if not analysis_results:
        logger.warning("Analysis API not available, using direct ontology server for entity extraction...")
        
        # Extract entities directly from case text
        case_text = case_details.get('content', '')
        entities = extract_case_entities_direct(case_text)
        
        if entities:
            # Create simulated analysis results
            analysis_results = {
                'status': 'success',
                'analysis': {
                    'entities': entities,
                    'principles': [],
                    'timeline': [],
                    'summary': f"This is a simulated analysis of case {case_id}."
                }
            }
            logger.info(f"Extracted {len(entities)} entities directly from case text")
        else:
            logger.error("Failed to extract entities from case text")
            sys.exit(1)
    
    # Print analysis report
    print_analysis_report(case_details, analysis_results)
    
    logger.info("Case analysis complete")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAnalysis interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
