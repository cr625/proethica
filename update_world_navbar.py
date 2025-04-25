#!/usr/bin/env python3
"""
Script to update the world_detail.html template to use the base.html navigation.
This ensures that the Ontology Editor link appears in the navigation bar on
world detail pages.
"""

import os
from pathlib import Path
import re

# Path to the world detail template
TEMPLATE_PATH = Path("app/templates/world_detail.html")
BASE_TEMPLATE_PATH = Path("app/templates/base.html")
BACKUP_DIR = Path("backups")

def create_backup(file_path):
    """Create a backup of the original file"""
    backup_path = BACKUP_DIR / f"{file_path.name}.mainav.bak"
    
    # Create backup directory if it doesn't exist
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir()
    
    with open(file_path, 'r') as original:
        with open(backup_path, 'w') as backup:
            backup.write(original.read())
    
    print(f"Created backup of {file_path} at {backup_path}")
    return backup_path

def get_base_navbar():
    """Extract the main navigation bar from base.html"""
    if not BASE_TEMPLATE_PATH.exists():
        print(f"Error: {BASE_TEMPLATE_PATH} does not exist")
        return None
    
    with open(BASE_TEMPLATE_PATH, 'r') as f:
        content = f.read()
    
    # Extract the navbar content
    navbar_pattern = re.compile(r'<ul\s+class="navbar-nav\s+me-auto">.*?</ul>', re.DOTALL)
    match = navbar_pattern.search(content)
    
    if not match:
        print("Error: Couldn't find the navigation bar in base.html")
        return None
    
    return match.group(0)

def update_world_template():
    """Update the world_detail.html to use the same navigation as base.html"""
    if not TEMPLATE_PATH.exists():
        print(f"Error: {TEMPLATE_PATH} does not exist")
        return False
    
    # Create backup
    backup_path = create_backup(TEMPLATE_PATH)
    
    # Get the base navbar
    base_navbar = get_base_navbar()
    if not base_navbar:
        return False
    
    # Read the world template
    with open(TEMPLATE_PATH, 'r') as f:
        content = f.read()
    
    # Find the existing navbar in world_detail.html
    navbar_pattern = re.compile(r'<ul\s+class="navbar-nav\s+me-auto">.*?</ul>', re.DOTALL)
    match = navbar_pattern.search(content)
    
    if not match:
        print("Error: Couldn't find the navigation bar in world_detail.html")
        return False
    
    # Replace the old navbar with the one from base.html
    updated_content = content.replace(match.group(0), base_navbar)
    
    # Write the updated content
    with open(TEMPLATE_PATH, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {TEMPLATE_PATH} to use the base.html navigation bar")
    return True

if __name__ == "__main__":
    print("Updating world_detail.html to use the base.html navigation bar...")
    result = update_world_template()
    if result:
        print("\n✅ Successfully updated the world detail page navigation!")
        print("\nThe changes made:")
        print("1. Added 'Ontology Editor' link to the main navigation bar on world detail pages")
        print("2. Ensured consistent navigation across all pages in the application")
        print("3. Created a backup of the original file")
        print("\nPlease restart the server to apply the changes.")
    else:
        print("\n❌ Failed to update the navigation bar. Please check the error messages above.")
