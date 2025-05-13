#!/usr/bin/env python3
# Script to fix all model files to use proper import patterns

import os
import sys
import shutil
import time
import glob

def backup_file(file_path):
    """Create a backup of the file"""
    backup_path = f"{file_path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup at {backup_path}")

def fix_model_files():
    """Fix imports in all model files to use app.models.db instead of app.db"""
    # Get all Python files in the models directory
    model_files = glob.glob("app/models/*.py")
    # Filter out __init__.py and __pycache__
    model_files = [f for f in model_files if "__init__" not in f and "__pycache__" not in f]
    
    fixed_count = 0
    for model_path in model_files:
        try:
            with open(model_path, 'r') as f:
                content = f.read()
            
            # Check if the file has the problematic import
            if "from app import db" in content:
                backup_file(model_path)
                
                # Replace import statement
                new_content = content.replace("from app import db", "from app.models import db")
                
                with open(model_path, 'w') as f:
                    f.write(new_content)
                
                print(f"Updated {model_path} to import db from app.models")
                fixed_count += 1
        except Exception as e:
            print(f"Error processing {model_path}: {str(e)}")
    
    print(f"Fixed {fixed_count} model files")
    return fixed_count

if __name__ == "__main__":
    print("Fixing imports in all model files...")
    num_fixed = fix_model_files()
    print(f"Import fixes completed! Updated {num_fixed} files.")
