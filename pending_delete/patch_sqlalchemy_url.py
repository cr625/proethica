#!/usr/bin/env python3
"""
Patch script that modifies app/__init__.py to handle escaped database URLs
This file adds a workaround for the SQLAlchemy URL parsing issue
"""

import os
import re
import sys
import importlib

def patch_create_app():
    """Patch the create_app function to handle escaped URLs"""
    app_init_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', '__init__.py')
    
    # Check if file exists
    if not os.path.exists(app_init_path):
        print(f"Error: {app_init_path} not found")
        return False
    
    # Read the current content
    with open(app_init_path, 'r') as f:
        content = f.read()
    
    # Check if already patched
    if "# SQLAlchemy URL fix" in content:
        print("app/__init__.py already patched")
        return True
    
    # Find the db.init_app(app) line
    db_init_pattern = r'([\s]*)db\.init_app\(app\)([\s]*)'
    match = re.search(db_init_pattern, content)
    
    if not match:
        print("Could not find db.init_app(app) in app/__init__.py")
        return False
    
    # Get the indentation level
    indent = match.group(1)
    trailing = match.group(2)
    
    # Create the patch code
    patch_code = f"{indent}# SQLAlchemy URL fix\n"
    patch_code += f"{indent}if app.config.get('SQLALCHEMY_DATABASE_URI') and '\\\\x3a' in app.config['SQLALCHEMY_DATABASE_URI']:\n"
    patch_code += f"{indent}    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('\\\\x3a', ':')\n"
    patch_code += f"{indent}    print(f\"Fixed escaped database URL: {{app.config['SQLALCHEMY_DATABASE_URI']}}\")\n"
    patch_code += f"{indent}db.init_app(app){trailing}"
    
    # Apply the patch
    patched_content = content.replace(match.group(0), patch_code)
    
    # Write back to the file
    with open(app_init_path, 'w') as f:
        f.write(patched_content)
    
    print(f"Successfully patched {app_init_path}")
    return True

if __name__ == "__main__":
    # Apply the patch
    success = patch_create_app()
    if success:
        print("Patch applied successfully")
    else:
        print("Failed to apply patch")
        sys.exit(1)
