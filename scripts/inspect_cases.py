#!/usr/bin/env python3
"""
Script to inspect NSPE cases data structure
"""

import json
import os
import argparse

def list_all_case_numbers(cases_file, show_all=False):
    """List all case numbers from the specified file."""
    try:
        # Load the cases
        with open(cases_file, 'r') as f:
            cases = json.load(f)
        
        print(f"Found {len(cases)} cases in {cases_file}")
        
        # Create a list of case numbers
        case_numbers = []
        for i, case in enumerate(cases):
            case_number = case.get("case_number", "N/A")
            if case_number != "N/A":
                case_numbers.append((i, case_number, case.get("title", "N/A")))
        
        # Sort by case number
        case_numbers.sort(key=lambda x: x[1])
        
        print(f"\nTotal unique case numbers: {len(case_numbers)}")
        if show_all:
            print("\nAll case numbers:")
            for index, case_number, title in case_numbers:
                print(f"Index: {index}, Case Number: {case_number}, Title: {title}")
        else:
            print("\nSample of case numbers:")
            for index, case_number, title in case_numbers[:10]:
                print(f"Index: {index}, Case Number: {case_number}, Title: {title}")
            
            if len(case_numbers) > 10:
                print(f"... and {len(case_numbers) - 10} more")
        
        return True
    except Exception as e:
        print(f"Error listing case numbers: {str(e)}")
        return False

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Inspect NSPE cases data structure")
    parser.add_argument('--all', action='store_true', help='Show all case numbers')
    parser.add_argument('--modern', action='store_true', help='Process modern NSPE cases')
    args = parser.parse_args()
    
    # Get the absolute path to the JSON file
    if args.modern:
        cases_file = os.path.join(os.getcwd(), "data", "modern_nspe_cases.json")
    else:
        cases_file = os.path.join(os.getcwd(), "data", "nspe_cases.json")
    
    try:
        # Load the cases
        with open(cases_file, 'r') as f:
            cases = json.load(f)
        
        print(f"Total cases: {len(cases)}")
        
        if cases:
            print(f"Keys in first case: {list(cases[0].keys())}")
            print("\nFirst 3 cases:")
            
            for i, case in enumerate(cases[:3]):
                case_id = case.get("id", "N/A")  # Default to N/A if no ID
                case_number = case.get("case_number", "N/A")
                title = case.get("title", "N/A")
                print(f"Index: {i}, ID: {case_id}, Case Number: {case_number}, Title: {title}")
        
        # List all case numbers
        list_all_case_numbers(cases_file, args.all)
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
