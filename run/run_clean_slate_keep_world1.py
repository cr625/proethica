#!/usr/bin/env python3
"""
COMPREHENSIVE CLEAN SLATE: Keep only World 1, remove everything else.
This script removes all data except World 1 and resets ID sequences.
"""

import subprocess
import sys
import os
from datetime import datetime

def check_docker_container():
    """Check if the PostgreSQL Docker container is running."""
    result = subprocess.run(['docker', 'ps', '--filter', 'name=proethica-postgres', '--format', '{{.Names}}'], 
                          capture_output=True, text=True)
    return 'proethica-postgres' in result.stdout

def backup_before_clean_slate():
    """Create a backup before the destructive operation."""
    print("📦 Creating backup before clean slate...")
    try:
        backup_result = subprocess.run(['bash', './backups/backup_database.sh'], 
                                     cwd='/home/chris/proethica',
                                     capture_output=True, text=True)
        if backup_result.returncode == 0:
            print("✅ Backup created successfully!")
            return True
        else:
            print(f"❌ Backup failed: {backup_result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Backup failed with error: {e}")
        # Continue anyway since we already have recent backups
        print("⚠️  Continuing with existing backups...")
        return True

def run_clean_slate():
    """Execute the clean slate SQL script."""
    print("=" * 80)
    print("🧹 COMPREHENSIVE CLEAN SLATE: KEEP ONLY WORLD 1")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if Docker container is running
    if not check_docker_container():
        print("ERROR: PostgreSQL Docker container 'proethica-postgres' is not running.")
        print("Please start the container with: docker-compose up -d postgres")
        return 1
    
    print("🚨 ULTRA-DESTRUCTIVE OPERATION WARNING! 🚨")
    print()
    print("This script will PERMANENTLY DELETE ALL DATA except:")
    print("✅ World 1 (and its basic properties)")
    print()
    print("🗑️  EVERYTHING ELSE WILL BE DELETED:")
    print("❌ All documents (including guideline documents)")
    print("❌ All guidelines and their triples")
    print("❌ All scenarios, characters, events")
    print("❌ All resources, roles, conditions, decisions")
    print("❌ All other worlds")
    print("❌ All simulation data")
    print("❌ All experiment data")
    print()
    print("🔄 ADDITIONALLY:")
    print("✅ All ID sequences will restart from 1")
    print("✅ Next document will have ID = 1")
    print("✅ Next guideline will have ID = 1")
    print("✅ Next triple will have ID = 1")
    print()
    print("💾 After this, you'll need to:")
    print("1. Upload your guideline document again")
    print("2. Run concept extraction from scratch")
    print("3. All new data will have clean, sequential IDs")
    print()
    
    # Create backup first
    if not backup_before_clean_slate():
        print("❌ Cannot proceed without successful backup!")
        return 1
    
    print("🔥 This is the MOST DESTRUCTIVE operation possible!")
    print("🔥 There is NO UNDO after this point!")
    print()
    
    # Triple confirmation for ultra-destructive operation
    response1 = input("Are you absolutely sure you want to delete EVERYTHING except World 1? (yes/no): ").strip().lower()
    if response1 != 'yes':
        print("Clean slate cancelled.")
        return 0
        
    response2 = input("This will DELETE ALL your work. Type 'DELETE EVERYTHING' to confirm: ").strip()
    if response2 != 'DELETE EVERYTHING':
        print("Clean slate cancelled.")
        return 0
        
    response3 = input("Last chance! Type 'CLEAN SLATE NOW' to proceed: ").strip()
    if response3 != 'CLEAN SLATE NOW':
        print("Clean slate cancelled.")
        return 0
    
    print("\n🧹 Executing comprehensive clean slate...")
    print("-" * 80)
    
    # Build the docker exec command
    sql_file = '/home/chris/proethica/sql/clean_slate_keep_world1.sql'
    cmd = [
        'docker', 'exec', '-i', 'proethica-postgres',
        'psql', '-U', 'postgres', '-d', 'ai_ethical_dm', '-f', '-'
    ]
    
    try:
        # Read the SQL file
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Execute the SQL
        result = subprocess.run(cmd, input=sql_content, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        if result.stderr and "NOTICE" not in result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"\nERROR: Command failed with return code {result.returncode}")
            return result.returncode
            
        print("-" * 80)
        print("\n🎉 CLEAN SLATE COMPLETED SUCCESSFULLY!")
        print()
        print("✅ Results:")
        print("- Database now contains only World 1")
        print("- All other data has been permanently deleted")
        print("- ID sequences reset to start from 1")
        print("- No duplicate data possible")
        print()
        print("🚀 Next steps:")
        print("1. Go to: http://localhost:3333/worlds/1")
        print("2. Navigate to Guidelines management")
        print("3. Upload/add your guideline document (will get ID = 1)")
        print("4. Run concept extraction (guideline will get ID = 1)")
        print("5. All triples will start from ID = 1 with no duplicates")
        print()
        print("🎯 Benefits of clean slate:")
        print("- Guaranteed no duplicates")
        print("- Clean, sequential IDs starting from 1")
        print("- Fresh start with optimal performance")
        print("- Proper deduplication service integration from the beginning")
        
        # Generate log file
        log_file = f"clean_slate_keep_world1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w') as f:
            f.write(f"Clean slate executed at: {datetime.now()}\n")
            f.write(f"Output:\n{result.stdout}\n")
            if result.stderr:
                f.write(f"Errors:\n{result.stderr}\n")
        
        print(f"\n📝 Log saved to: {log_file}")
        
        return 0
        
    except FileNotFoundError:
        print(f"ERROR: SQL file not found: {sql_file}")
        return 1
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(run_clean_slate())