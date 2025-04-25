#!/usr/bin/env python3
"""
Script to update navigation bar in the world detail page template
to include the Ontology Editor link for consistent navigation.
"""

import os
from pathlib import Path
import re

# Path to the world detail template
TEMPLATE_PATH = Path("app/templates/world_detail.html")
BACKUP_DIR = Path("backups")

def create_backup(file_path):
    """Create a backup of the original file"""
    backup_path = BACKUP_DIR / f"{file_path.name}.nav.bak"
    
    # Create backup directory if it doesn't exist
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir()
    
    with open(file_path, 'r') as original:
        with open(backup_path, 'w') as backup:
            backup.write(original.read())
    
    print(f"Created backup of {file_path} at {backup_path}")
    return backup_path

def update_navigation_bar():
    """
    Update the navigation bar in the world detail template to include
    the Ontology Editor link for consistent navigation.
    """
    if not TEMPLATE_PATH.exists():
        print(f"Error: {TEMPLATE_PATH} does not exist")
        return False
    
    # Create backup
    backup_path = create_backup(TEMPLATE_PATH)
    
    # Read the template
    with open(TEMPLATE_PATH, 'r') as f:
        content = f.read()
    
    # Find the navigation bar section
    nav_pattern = re.compile(r'<ul\s+class="navbar-nav\s+me-auto">.*?</ul>', re.DOTALL)
    nav_match = nav_pattern.search(content)
    
    if not nav_match:
        print("Error: Navigation bar not found in the template")
        return False
    
    # Extract the navigation bar content
    nav_content = nav_match.group(0)
    
    # Check if the Ontology Editor link already exists
    if 'href="/ontology-editor"' in nav_content:
        print("Ontology Editor link already exists in the navigation bar")
        return True
    
    # Find the last nav-item
    last_item_pattern = re.compile(r'<li\s+class="nav-item">.*?</li>\s*</ul>', re.DOTALL)
    last_item_match = last_item_pattern.search(nav_content)
    
    if not last_item_match:
        print("Error: Last navigation item not found")
        return False
    
    # Extract the last item
    last_item = last_item_match.group(0)
    
    # Create the new Ontology Editor nav item
    ontology_editor_item = """            <li class="nav-item">
                                <a class="nav-link" href="/ontology-editor">Ontology Editor</a>
                            </li>
"""
    
    # Insert the new item before the last </ul>
    updated_nav_content = nav_content.replace(last_item, ontology_editor_item + last_item)
    
    # Replace the original navigation bar with the updated one
    updated_content = content.replace(nav_content, updated_nav_content)
    
    # Write the updated content back to the file
    with open(TEMPLATE_PATH, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {TEMPLATE_PATH} with the Ontology Editor link")
    return True

if __name__ == "__main__":
    print("Updating navigation bar in the world detail template...")
    result = update_navigation_bar()
    if result:
        print("\n✅ Successfully updated the navigation bar!")
        print("\nThe changes made:")
        print("1. Added 'Ontology Editor' link to the navigation bar in world_detail.html")
        print("2. Created a backup of the original file")
        print("\nPlease restart the server to apply the changes.")
    else:
        print("\n❌ Failed to update the navigation bar. Please check the error messages above.")
