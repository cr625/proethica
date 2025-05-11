#!/usr/bin/env python3
"""
Batch process NSPE cases using McLaren's extensional definition approach.

This script can process both original and modern NSPE cases in batch mode.
It uses the direct processing approach to avoid Flask-SQLAlchemy URL parsing issues.
"""

import os
import sys
import json
import logging
import argparse
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("batch_process_nspe_cases")

def load_cases(file_path: str) -> List[Dict[str, Any]]:
    """Load cases from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            cases = json.load(f)
        logger.info(f"Loaded {len(cases)} cases from {file_path}")
        return cases
    except Exception as e:
        logger.error(f"Error loading cases from {file_path}: {str(e)}")
        raise

def process_case(case_number: str, is_modern: bool = False) -> bool:
    """Process a single case using the direct processing script."""
    try:
        modern_flag = "--modern" if is_modern else ""
        command = f"./setup_ontology_case_analysis_direct.sh \"{case_number}\" {modern_flag}"
        logger.info(f"Executing: {command}")
        
        result = os.system(command)
        if result == 0:
            logger.info(f"Successfully processed case {case_number}")
            return True
        else:
            logger.error(f"Failed to process case {case_number}, exit code: {result}")
            return False
    except Exception as e:
        logger.error(f"Error processing case {case_number}: {str(e)}")
        return False

def process_cases_in_batch(
    cases: List[Dict[str, Any]], 
    is_modern: bool = False, 
    max_workers: int = 1,
    filter_case_numbers: Optional[List[str]] = None
) -> Tuple[int, int]:
    """
    Process multiple cases in batch, optionally in parallel.
    
    Args:
        cases: List of case dictionaries
        is_modern: Whether these are modern NSPE cases
        max_workers: Maximum number of parallel workers (1 = sequential)
        filter_case_numbers: Optional list of case numbers to process (if None, process all)
    
    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0
    
    # Filter cases if needed
    if filter_case_numbers:
        filtered_cases = [
            case for case in cases 
            if case.get("case_number", "") in filter_case_numbers
        ]
        logger.info(f"Filtered {len(filtered_cases)} cases from {len(cases)} total cases")
        cases = filtered_cases
    
    case_numbers = [case.get("case_number", "") for case in cases]
    
    if max_workers > 1:
        # Process cases in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_case = {
                executor.submit(process_case, case_number, is_modern): case_number
                for case_number in case_numbers if case_number
            }
            
            for future in concurrent.futures.as_completed(future_to_case):
                case_number = future_to_case[future]
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    logger.error(f"Exception processing case {case_number}: {str(e)}")
                    failure_count += 1
    else:
        # Process cases sequentially
        for case_number in case_numbers:
            if case_number:
                if process_case(case_number, is_modern):
                    success_count += 1
                else:
                    failure_count += 1
    
    return success_count, failure_count

def main():
    """Main entry point for the batch processing script."""
    parser = argparse.ArgumentParser(
        description="Batch process NSPE cases using McLaren's extensional definition approach"
    )
    parser.add_argument(
        '--modern', action='store_true', 
        help='Process modern NSPE cases instead of original ones'
    )
    parser.add_argument(
        '--workers', type=int, default=1,
        help='Number of worker threads for parallel processing (default: 1)'
    )
    parser.add_argument(
        '--case-numbers', type=str, nargs='+',
        help='Specific case numbers to process (e.g., "89-7-1" "76-4-1")'
    )
    parser.add_argument(
        '--limit', type=int,
        help='Limit the number of cases to process'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be processed without actually processing'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Show verbose output'
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine the source file
    if args.modern:
        cases_file = os.path.join(os.getcwd(), "data", "modern_nspe_cases.json")
        logger.info("Processing modern NSPE cases")
    else:
        cases_file = os.path.join(os.getcwd(), "data", "nspe_cases.json")
        logger.info("Processing original NSPE cases")
    
    # Load cases
    cases = load_cases(cases_file)
    
    # Apply limit if specified
    if args.limit and args.limit > 0:
        cases = cases[:args.limit]
        logger.info(f"Limited to first {args.limit} cases")
    
    if args.case_numbers:
        logger.info(f"Filtering to process only specified case numbers: {args.case_numbers}")
    
    # If dry run, just show what would be processed
    if args.dry_run:
        case_numbers = [case.get("case_number", "N/A") for case in cases]
        if args.case_numbers:
            case_numbers = [cn for cn in case_numbers if cn in args.case_numbers]
        
        logger.info(f"Dry run - would process {len(case_numbers)} cases:")
        for i, case_number in enumerate(case_numbers):
            title = next((case.get("title", "N/A") for case in cases if case.get("case_number") == case_number), "N/A")
            logger.info(f"  {i+1}. {case_number}: {title}")
        return 0
    
    # Process the cases
    success_count, failure_count = process_cases_in_batch(
        cases,
        is_modern=args.modern,
        max_workers=args.workers,
        filter_case_numbers=args.case_numbers
    )
    
    logger.info(f"Processing complete. Successfully processed {success_count} cases, failed to process {failure_count} cases")
    
    if failure_count > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
