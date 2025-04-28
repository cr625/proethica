#!/usr/bin/env python3
"""
Script to document the scripts cleanup in CLAUDE.md
"""

import os
import datetime
from pathlib import Path

def update_claude_md():
    # Get current date in required format
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Read the current CLAUDE.md
    with open("CLAUDE.md", "r") as f:
        content = f.read()
    
    # Create the update entry
    entry = f"""## {date_str} - Scripts Directory Cleanup

### Actions Taken

1. **Removed Unused Scripts**
   - Removed early development scripts that are no longer needed
   - Preserved essential scripts for API testing, environment management, and system utilities
   - Created backup of all removed scripts in scripts_backup_* directory

2. **Removed Archive Directory**
   - Removed the scripts/archive directory as version control can be used if needed
   - Archive contained old population scripts and pre-RDF migration tools

3. **Kept Essential Scripts**
   - Maintained all Claude API verification and testing scripts
   - Preserved database management utilities
   - Kept ontology management and system maintenance scripts

### Key Scripts Preserved

- **API Management**: verify_anthropic_fix.py, test_claude_with_env.py, try_anthropic_bearer.py
- **Environment Setup**: run_with_env.sh, git_protect_keys.sh
- **Database Utilities**: check_db.py, create_admin_user.py
- **Ontology Tools**: check_ontology.py, fix_ontology_automatically.py, fix_ontology_validation.py

### Benefits

- **Cleaner Directory Structure**: Removed obsolete and one-time fix scripts
- **Better Organization**: Focused on keeping only currently useful scripts
- **Improved Maintainability**: Easier to find relevant scripts
- **Version Safety**: All removed files were backed up before deletion

### Implementation

The cleanup was implemented using a dedicated script that:
1. Identified essential scripts to preserve
2. Created backups of all files before removal
3. Generated a detailed log of all operations
4. Removed the archive directory and unneeded scripts
"""

    # Insert the entry after the first line (assumed to be the title)
    if "\n" in content:
        first_line_end = content.find("\n") + 1
        updated_content = content[:first_line_end] + entry + "\n\n" + content[first_line_end:]
    else:
        updated_content = content + "\n\n" + entry

    # Write back to CLAUDE.md
    with open("CLAUDE.md", "w") as f:
        f.write(updated_content)
    
    print(f"Successfully updated CLAUDE.md with scripts cleanup documentation")

if __name__ == "__main__":
    update_claude_md()
