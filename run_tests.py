#!/usr/bin/env python3
"""
Script to run all tests for the application.
"""
import os
import sys
import pytest


def main():
    """Run all tests."""
    # Set the environment to testing
    os.environ['FLASK_ENV'] = 'testing'
    
    # Add arguments for verbose output if specified
    args = ['-v'] if '--verbose' in sys.argv or '-v' in sys.argv else []
    
    # Add arguments for specific test file if specified
    for arg in sys.argv[1:]:
        if arg.startswith('tests/') and not arg.startswith('-'):
            args.append(arg)
    
    # Run the tests
    exit_code = pytest.main(args)
    
    # Return the exit code
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
