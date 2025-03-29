#!/usr/bin/env python3
"""
Script to run all tests for the application with PostgreSQL.

This script delegates to scripts/run_tests_with_pg.py which ensures the
PostgreSQL test database exists and is properly configured before running tests.
"""
import os
import sys
import subprocess

def main():
    """Run all tests with PostgreSQL database."""
    # Get the path to the run_tests_with_pg.py script
    script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'run_tests_with_pg.py')
    
    # Build arguments to pass to the script
    args = [sys.executable, script_path]
    
    # Add verbose flag if specified
    if '--verbose' in sys.argv or '-v' in sys.argv:
        args.append('--verbose')
    
    # Add specific test path if provided
    for arg in sys.argv[1:]:
        if arg.startswith('tests/') and not arg.startswith('-'):
            args.append(arg)
            break
    
    # Run the script
    result = subprocess.run(args)
    
    # Return the exit code
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())
