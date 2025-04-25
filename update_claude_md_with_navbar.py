#!/usr/bin/env python3
"""
Script to update the CLAUDE.md file with information about the
navigation bar improvements.
"""

import os
from datetime import datetime
import re

def update_claude_md():
    """Update the CLAUDE.md file with today's navigation bar improvements"""
    claude_md_path = "CLAUDE.md"
    
    # Check if file exists
    if not os.path.exists(claude_md_path):
        print(f"Error: {claude_md_path} does not exist")
        return False
    
    # Read the current file content
    with open(claude_md_path, 'r') as f:
        content = f.read()
    
    # Get today's date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if today's entry already exists
    today_pattern = re.compile(rf"## {today}")
    match = today_pattern.search(content)
    
    if match:
        # Find where the "Next Steps" section begins in today's entry
        next_steps_pattern = re.compile(r"### Next Steps")
        next_steps_match = next_steps_pattern.search(content)
        
        if next_steps_match:
            # Position to insert our new item just before "Next Steps"
            pos = next_steps_match.start()
            
            # Create the new navigation bar improvement section
            navbar_section = """
4. **Made Navigation Consistent Across App**
   - Added Ontology Editor link to world detail page navigation
   - Ensured consistent user experience throughout the application
   - Improved discoverability of the ontology editor functionality
   - Streamlined workflow between world details and ontology editing

"""
            
            # Insert the new section
            updated_content = content[:pos] + navbar_section + content[pos:]
            
            # Write the updated content back to the file
            with open(claude_md_path, 'w') as f:
                f.write(updated_content)
            
            print(f"Updated {claude_md_path} with navigation bar improvements")
            return True
        else:
            print(f"Error: Next Steps section not found in today's entry")
            return False
    else:
        print(f"Error: Today's entry ({today}) not found in the file")
        return False

if __name__ == "__main__":
    print("Updating CLAUDE.md with navigation bar improvements...")
    update_claude_md()
    print("Done!")
