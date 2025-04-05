#!/usr/bin/env python
"""
Test runner script for ProEthica.
This script sets up the PostgreSQL test database and runs the tests.
"""

import os
import sys
import argparse
import subprocess
import pytest

# Add the parent directory to the Python path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up the environment for testing
os.environ['FLASK_ENV'] = 'testing'

def setup_test_database():
    """Set up the test database."""
    script_path = os.path.join(os.path.dirname(__file__), 'manage_test_db.py')
    
    print("Setting up test database...")
    result = subprocess.run(['python', script_path, '--create'], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error setting up test database: {result.stderr}")
        sys.exit(1)
    
    print("Test database setup complete.")

def run_tests(test_path=None, verbose=False):
    """Run the tests."""
    # Build pytest arguments
    pytest_args = []
    
    # Add verbosity
    if verbose:
        pytest_args.append('-v')
    
    # Add test path if provided
    if test_path:
        pytest_args.append(test_path)
    else:
        # Default to running all tests
        pytest_args.append('tests/')
    
    print(f"Running tests: pytest {' '.join(pytest_args)}")
    return pytest.main(pytest_args)

def main():
    """Main function to process command line arguments and run tests."""
    parser = argparse.ArgumentParser(description="Run ProEthica tests with PostgreSQL.")
    
    # Define arguments
    parser.add_argument(
        'test_path', 
        nargs='?', 
        help="Path to test file or directory (e.g., 'tests/test_mcp_api.py')"
    )
    parser.add_argument(
        '--verbose', '-v', 
        action='store_true', 
        help="Verbose output"
    )
    parser.add_argument(
        '--setup-only', 
        action='store_true', 
        help="Only setup the test database without running tests"
    )
    
    args = parser.parse_args()
    
    # Set up test database
    setup_test_database()
    
    if args.setup_only:
        print("Test database setup complete. Exiting without running tests.")
        return 0
    
    # Run tests
    return run_tests(args.test_path, args.verbose)

if __name__ == "__main__":
    sys.exit(main())
