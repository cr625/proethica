#!/usr/bin/env python3
"""
Document the updates made to the ontology editor header templates in CLAUDE.md.
"""
import os
import datetime

# Get current date
today = datetime.datetime.now().strftime("%Y-%m-%d")

# Documentation to add
header_update_doc = f"""## {today} - Ontology Editor Header Update

### Implemented Changes

1. **Updated Ontology Editor Header Style**
   - Updated the header of the ontology editor pages to match the main application style
   - Changed from dark navbar to light navbar with bottom border to match ProEthica style
   - Updated branding from "BFO Ontology Editor" to "ProEthica Ontology" for consistent identity
   - Added a link back to the main application for improved navigation
   - Applied styling consistent with the main application's header design

2. **Enhanced Visual Consistency Across Templates**
   - Applied consistent styling to all ontology editor templates:
     - editor.html (main ontology editor)
     - hierarchy.html (ontology hierarchy visualization)
     - visualize.html (ontology visualization)
   - Added header div with appropriate padding and bottom border
   - Ensured consistent navbar with proper styling and links

3. **Improved Navigation Between Views**
   - Added clear navigation between ontology editor views
   - Added link to main application from all ontology editor pages
   - Enhanced visual hierarchy with proper active state for current view
   - Maintained modularity to keep the ontology editor as a separate component

### Benefits

- **Improved User Experience**: Users now experience consistent styling throughout the application
- **Better Navigation**: Clearer relationship between ontology editor and main application
- **Consistent Branding**: All pages now reflect the ProEthica brand identity
- **Maintained Modularity**: Updates preserve the modular architecture of the application

### Implementation Details

The header updates were implemented using Python scripts that:
1. Created proper backups of all templates before modification
2. Added CSS styling to match the main application's header design
3. Updated the navbar component to use light styling with proper branding
4. Maintained all existing functionality while improving visual consistency

These changes improve the overall user experience while maintaining the separation 
of concerns between the ontology editor module and the main application.
"""

# Read the current CLAUDE.md content
claude_md_path = "CLAUDE.md"
with open(claude_md_path, "r") as f:
    content = f.read()

# Insert the new documentation after the first line that contains "# ProEthica Development Log"
lines = content.split("\n")
insert_pos = 0

for i, line in enumerate(lines):
    if "# ProEthica Development Log" in line:
        insert_pos = i + 1
        break

if insert_pos > 0:
    updated_content = "\n".join(lines[:insert_pos]) + "\n\n" + header_update_doc + "\n\n" + "\n".join(lines[insert_pos:])

    # Write the updated content back to CLAUDE.md
    with open(claude_md_path, "w") as f:
        f.write(updated_content)
    
    print(f"Documentation added to {claude_md_path}")
else:
    print(f"Error: Could not find insertion point in {claude_md_path}")
