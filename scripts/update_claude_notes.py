#!/usr/bin/env python3
"""
Update CLAUDE.md with latest development notes
"""

import os
from datetime import datetime

def update_claude_notes():
    """Update the CLAUDE.md file with the latest development notes"""
    
    # Date for the new entry
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Read the existing content
    claude_md_path = os.path.join(os.path.dirname(__file__), '..', 'CLAUDE.md')
    
    try:
        with open(claude_md_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        # Create a new file if it doesn't exist
        content = "# ProEthica Development Notes\n\n"
    
    # Create the entry
    entry = f"""
## {today} - Ontology File Fix and MCP Server Configuration

### Issue
The ProEthica application was started using `start_proethica_updated.sh`, but the database entries were not showing up. Specifically, the BFO ontology and proethica-intermediate ontology were not accessible through the ontology editor.

### Investigation
1. Initial diagnostics showed the MCP server could access the ontologies, but wasn't returning any entities.
2. Testing revealed format issues with the TTL files:
   - The ontology files (bfo.ttl, proethica-intermediate.ttl, and engineering-ethics.ttl) had unexpected '+' characters at line endings
   - These characters prevented proper parsing by RDFLib

3. Path inconsistency discovered:
   - The MCP server was looking for proethica-intermediate.ttl at `/home/chris/ai-ethical-dm/mcp/ontology/` 
   - But the file was located at `/home/chris/ai-ethical-dm/ontologies/`

### Solution
1. Created and ran a script `clean_ttl_files.py` to remove the problematic '+' characters from the TTL files
2. Added symbolic links from the main ontologies directory to the mcp/ontology directory:
   ```bash
   mkdir -p mcp/ontology
   ln -sf "$PWD/ontologies/bfo.ttl" mcp/ontology/bfo.ttl
   ln -sf "$PWD/ontologies/proethica-intermediate.ttl" mcp/ontology/proethica-intermediate.ttl
   ln -sf "$PWD/ontologies/engineering-ethics.ttl" mcp/ontology/engineering-ethics.ttl
   ```
3. Restarted the unified ontology server with the script `restart_unified_ontology_server.sh`

### Results
- The MCP server now successfully accesses all ontologies (bfo, proethica-intermediate, and engineering-ethics)
- Entity counts are as expected:
  - bfo: 36 entities
  - proethica-intermediate: 47 entities
  - engineering-ethics: 113 entities
- The ontology editor can now properly display these ontologies

### Scripts Created/Updated
1. `scripts/clean_ttl_files.py` - Cleans TTL files by removing problematic characters
2. `scripts/check_all_ontologies.py` - Verifies that ontology files can be parsed correctly
3. `scripts/test_bfo_parsing.py` - Tests specific parsing of the BFO ontology
4. `scripts/restart_unified_ontology_server.sh` - Properly restarts the unified ontology server

### Future Recommendations
1. Implement regular validation of ontology files as part of the build/start process
2. Consider standardizing the paths for ontology files to prevent path inconsistencies
3. Add error handling in MCP server to detect and report TTL parsing issues more clearly
"""
    
    # Check if the entry already exists
    if f"## {today} - Ontology File Fix and MCP Server Configuration" in content:
        print("Entry already exists in CLAUDE.md")
        return
    
    # Add the new entry after the header
    if "# ProEthica Development Notes" in content:
        content = content.replace("# ProEthica Development Notes\n\n", "# ProEthica Development Notes\n\n" + entry)
    else:
        content = "# ProEthica Development Notes\n\n" + entry + content
    
    # Write the updated content
    with open(claude_md_path, 'w') as f:
        f.write(content)
    
    print(f"Updated {claude_md_path} with the latest development notes")

if __name__ == "__main__":
    update_claude_notes()
