#!/usr/bin/env python
"""
Database Schema Verification Utility

This script verifies that the database schema is properly set up for the AI Ethical DM application.
Run this script when:
1. After updating the codebase with new models or schema changes
2. After database migrations
3. When experiencing database-related issues
4. Before deploying to a new environment

It will check and, if necessary, create or update tables and columns required by the application.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

def main():
    """Run database schema verification."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Verify and update database schema for AI Ethical DM")
    parser.add_argument('--check-only', action='store_true', 
                        help="Check schema without making changes")
    parser.add_argument('--database-url', type=str,
                        help="Database URL (will use DATABASE_URL env var if not provided)")
    args = parser.parse_args()

    # Load environment variables
    if os.path.exists('.env'):
        load_dotenv()

    # Get database URL
    db_url = args.database_url or os.environ.get('DATABASE_URL')
    if not db_url:
        db_url = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        print(f"No database URL provided, using default: {db_url}")
    
    # Set environment variable for other modules
    os.environ['DATABASE_URL'] = db_url
    
    print(f"Verifying database schema using: {db_url}")
    
    # Import and run schema verification
    from scripts.ensure_schema import ensure_schema
    
    print("Starting schema verification...")
    success = ensure_schema(not args.check_only)
    
    # Report results
    if success:
        print("\n✅ Database schema verification completed successfully.")
        if args.check_only:
            print("No changes were made (--check-only flag was used).")
        else:
            print("Any necessary changes have been applied.")
        sys.exit(0)
    else:
        print("\n❌ Schema verification completed with issues.")
        print("Some tables or columns could not be verified or created.")
        print("See the logs above for details.")
        sys.exit(1)

if __name__ == '__main__':
    main()
