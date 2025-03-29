#!/usr/bin/env python3
"""
Script to view and search NSPE Board of Ethical Review cases.

This script allows you to view details of both historical cases referenced in 
McLaren's 2003 paper and modern ethical cases, including their relationships
and operationalization techniques.
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from tabulate import tabulate

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Constants
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
NSPE_CASES_FILE = os.path.join(DATA_DIR, "nspe_cases.json")
MODERN_CASES_FILE = os.path.join(DATA_DIR, "modern_nspe_cases.json")

def load_cases(include_modern: bool = True) -> List[Dict[str, Any]]:
    """
    Load case studies from the JSON files.
    
    Args:
        include_modern: Whether to include modern cases (default: True)
        
    Returns:
        List of dictionaries with case details
    """
    all_cases = []
    
    # Load historical McLaren cases
    try:
        with open(NSPE_CASES_FILE, 'r', encoding='utf-8') as f:
            historical_cases = json.load(f)
            print(f"Loaded {len(historical_cases)} historical cases")
            all_cases.extend(historical_cases)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading historical cases from {NSPE_CASES_FILE}: {str(e)}")
    
    # Load modern cases if requested
    if include_modern and os.path.exists(MODERN_CASES_FILE):
        try:
            with open(MODERN_CASES_FILE, 'r', encoding='utf-8') as f:
                modern_cases = json.load(f)
                print(f"Loaded {len(modern_cases)} modern cases")
                all_cases.extend(modern_cases)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading modern cases from {MODERN_CASES_FILE}: {str(e)}")
    
    return all_cases

def list_cases(cases: List[Dict[str, Any]]) -> None:
    """
    List all cases in a tabular format.
    
    Args:
        cases: List of cases to display
    """
    if not cases:
        print("No cases found.")
        return
    
    table_data = []
    for case in cases:
        # Extract fields for the table
        table_data.append([
            case.get('case_number', 'Unknown'),
            case.get('title', 'Unknown Title'),
            case.get('year', 'Unknown'),
            case.get('metadata', {}).get('outcome', 'Unknown'),
            ', '.join(case.get('metadata', {}).get('principles', []))[:50] + ('...' if len(', '.join(case.get('metadata', {}).get('principles', []))) > 50 else ''),
            ', '.join(case.get('metadata', {}).get('operationalization_techniques', []))[:50] + ('...' if len(', '.join(case.get('metadata', {}).get('operationalization_techniques', []))) > 50 else '')
        ])
    
    # Print table
    headers = ["Case #", "Title", "Year", "Outcome", "Principles", "Operationalization Techniques"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def view_case_details(cases: List[Dict[str, Any]], case_number: str) -> None:
    """
    View detailed information about a specific case.
    
    Args:
        cases: List of cases
        case_number: Case number to view
    """
    for case in cases:
        if case.get('case_number') == case_number:
            print(f"\n===== CASE {case.get('case_number')}: {case.get('title')} ({case.get('year')}) =====\n")
            
            print("CASE DESCRIPTION:")
            print(case.get('full_text', 'No description available.'))
            print("\nOUTCOME:")
            print(case.get('metadata', {}).get('outcome', 'Unknown'))
            
            print("\nETHICAL PRINCIPLES:")
            for principle in case.get('metadata', {}).get('principles', []):
                print(f"- {principle}")
            
            print("\nCODES CITED:")
            for code in case.get('metadata', {}).get('codes_cited', []):
                print(f"- {code}")
            
            print("\nRELATED CASES:")
            for related_case in case.get('metadata', {}).get('related_cases', []):
                print(f"- {related_case}")
            
            print("\nOPERATIONALIZATION TECHNIQUES:")
            for technique in case.get('metadata', {}).get('operationalization_techniques', []):
                print(f"- {technique}")
            
            print("\nBOARD ANALYSIS:")
            print(case.get('metadata', {}).get('board_analysis', 'No analysis available.'))
            
            return
    
    print(f"Case {case_number} not found.")

def find_related_cases(cases: List[Dict[str, Any]], case_number: str) -> None:
    """
    Find and display cases related to a specific case.
    
    Args:
        cases: List of cases
        case_number: Case number to find related cases for
    """
    # Find the specified case
    target_case = None
    for case in cases:
        if case.get('case_number') == case_number:
            target_case = case
            break
    
    if not target_case:
        print(f"Case {case_number} not found.")
        return
    
    # Get cases that reference this case
    references_to_case = []
    for case in cases:
        if case.get('case_number') != case_number:
            if case_number in case.get('metadata', {}).get('related_cases', []):
                references_to_case.append(case.get('case_number'))
    
    # Get cases referenced by this case
    references_from_case = target_case.get('metadata', {}).get('related_cases', [])
    
    print(f"\nRelationships for Case {case_number}:")
    
    print("\nCases referenced by this case:")
    if references_from_case:
        for ref_case in references_from_case:
            print(f"- {ref_case}")
    else:
        print("None")
    
    print("\nCases that reference this case:")
    if references_to_case:
        for ref_case in references_to_case:
            print(f"- {ref_case}")
    else:
        print("None")

def search_cases(cases: List[Dict[str, Any]], query: str) -> None:
    """
    Search for cases matching a query.
    
    Args:
        cases: List of cases
        query: Search query (case-insensitive)
    """
    query = query.lower()
    matches = []
    
    for case in cases:
        # Check various fields for matches
        if (query in case.get('title', '').lower() or
            query in case.get('full_text', '').lower() or
            query in str(case.get('metadata', {}).get('principles', [])).lower() or
            query in str(case.get('metadata', {}).get('operationalization_techniques', [])).lower() or
            query in str(case.get('metadata', {}).get('board_analysis', '')).lower()):
            matches.append(case)
    
    if matches:
        print(f"Found {len(matches)} cases matching '{query}':")
        list_cases(matches)
    else:
        print(f"No cases found matching '{query}'.")

def search_by_operationalization(cases: List[Dict[str, Any]], technique: str) -> None:
    """
    Find cases that use a specific operationalization technique.
    
    Args:
        cases: List of cases
        technique: Operationalization technique to search for
    """
    technique = technique.lower()
    matches = []
    
    for case in cases:
        techniques = [t.lower() for t in case.get('metadata', {}).get('operationalization_techniques', [])]
        if any(technique in t for t in techniques):
            matches.append(case)
    
    if matches:
        print(f"Found {len(matches)} cases using '{technique}' operationalization technique:")
        list_cases(matches)
    else:
        print(f"No cases found using '{technique}' operationalization technique.")

def search_by_principle(cases: List[Dict[str, Any]], principle: str) -> None:
    """
    Find cases that involve a specific ethical principle.
    
    Args:
        cases: List of cases
        principle: Ethical principle to search for
    """
    principle = principle.lower()
    matches = []
    
    for case in cases:
        principles = [p.lower() for p in case.get('metadata', {}).get('principles', [])]
        if any(principle in p for p in principles):
            matches.append(case)
    
    if matches:
        print(f"Found {len(matches)} cases involving '{principle}' principle:")
        list_cases(matches)
    else:
        print(f"No cases found involving '{principle}' principle.")

def show_operationalization_examples(cases: List[Dict[str, Any]], technique: str) -> None:
    """
    Show examples of how a specific operationalization technique is used.
    
    Args:
        cases: List of cases
        technique: Operationalization technique to show examples for
    """
    technique = technique.lower()
    examples = []
    
    for case in cases:
        techniques = [t.lower() for t in case.get('metadata', {}).get('operationalization_techniques', [])]
        if any(technique in t for t in techniques):
            examples.append({
                'case_number': case.get('case_number'),
                'title': case.get('title'),
                'analysis': case.get('metadata', {}).get('board_analysis', 'No analysis available.')
            })
    
    if examples:
        print(f"\nExamples of '{technique}' operationalization technique:\n")
        for i, example in enumerate(examples, 1):
            print(f"Example {i}: Case {example['case_number']} - {example['title']}")
            print(f"Board Analysis: {example['analysis']}\n")
            if i < len(examples):
                print("-" * 80 + "\n")
    else:
        print(f"No examples found for '{technique}' operationalization technique.")

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='View and search NSPE Ethical Review cases')
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all cases')
    list_parser.add_argument('--historical-only', '-H', action='store_true', 
                           help='List only historical McLaren cases')
    list_parser.add_argument('--modern-only', '-m', action='store_true',
                           help='List only modern cases')
    
    # View command
    view_parser = subparsers.add_parser('view', help='View details of a specific case')
    view_parser.add_argument('case_number', type=str, help='Case number to view (e.g., 89-7-1)')
    
    # Related command
    related_parser = subparsers.add_parser('related', help='Find cases related to a specific case')
    related_parser.add_argument('case_number', type=str, help='Case number to find related cases for')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for cases matching a query')
    search_parser.add_argument('query', type=str, help='Search query')
    search_parser.add_argument('--historical-only', '-H', action='store_true',
                             help='Search only historical McLaren cases')
    search_parser.add_argument('--modern-only', '-m', action='store_true',
                             help='Search only modern cases')
    
    # Search by operationalization technique command
    op_parser = subparsers.add_parser('op-technique', help='Find cases using a specific operationalization technique')
    op_parser.add_argument('technique', type=str, help='Operationalization technique to search for')
    op_parser.add_argument('--historical-only', '-H', action='store_true',
                         help='Search only historical McLaren cases')
    op_parser.add_argument('--modern-only', '-m', action='store_true',
                         help='Search only modern cases')
    
    # Search by principle command
    principle_parser = subparsers.add_parser('principle', help='Find cases involving a specific ethical principle')
    principle_parser.add_argument('principle', type=str, help='Ethical principle to search for')
    principle_parser.add_argument('--historical-only', '-H', action='store_true',
                                help='Search only historical McLaren cases')
    principle_parser.add_argument('--modern-only', '-m', action='store_true',
                                help='Search only modern cases')
    
    # Show operationalization examples command
    examples_parser = subparsers.add_parser('examples', help='Show examples of an operationalization technique')
    examples_parser.add_argument('technique', type=str, help='Operationalization technique to show examples for')
    examples_parser.add_argument('--historical-only', '-H', action='store_true',
                               help='Show examples only from historical McLaren cases')
    examples_parser.add_argument('--modern-only', '-m', action='store_true',
                               help='Show examples only from modern cases')
    
    args = parser.parse_args()
    
    # Determine which case sets to load
    include_modern = True
    if hasattr(args, 'historical_only') and args.historical_only:
        include_modern = False
    
    # Load cases
    cases = load_cases(include_modern=include_modern)
    if not cases:
        sys.exit(1)
    
    # Filter to only modern cases if requested
    if hasattr(args, 'modern_only') and args.modern_only:
        modern_cases = [case for case in cases if case.get('scraped_at', '').startswith('2025')]
        if modern_cases:
            cases = modern_cases
        else:
            print("No modern cases found.")
            sys.exit(1)
    
    # Execute appropriate command
    if args.command == 'list':
        list_cases(cases)
    elif args.command == 'view':
        view_case_details(cases, args.case_number)
    elif args.command == 'related':
        find_related_cases(cases, args.case_number)
    elif args.command == 'search':
        search_cases(cases, args.query)
    elif args.command == 'op-technique':
        search_by_operationalization(cases, args.technique)
    elif args.command == 'principle':
        search_by_principle(cases, args.principle)
    elif args.command == 'examples':
        show_operationalization_examples(cases, args.technique)
    else:
        # Default to listing cases if no command is provided
        list_cases(cases)

if __name__ == '__main__':
    main()
