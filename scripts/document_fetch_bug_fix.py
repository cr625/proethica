#!/usr/bin/env python3
"""
Script to document the fetch bug fix in CLAUDE.md.
"""
import os
import sys
from datetime import datetime

def update_claude_md():
    """
    Update the CLAUDE.md file with information about the fetch bug fix.
    """
    print("Updating CLAUDE.md with fetch bug fix information...")
    
    # Get current date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create content to add
    new_content = f"""
## {today} - Fixed JavaScript Fetch Chain Bug in Diff Viewer

### Issue Fixed

Fixed a critical bug in the diff viewer's fetch chain that was causing HTTP requests to fail when comparing versions. The error was:

```
Error loading diff: Error: Failed to load diff
```

### Root Cause Analysis

The bug was in the `loadDiff` function of `diff.js` where `response.json()` was being called twice in the Promise chain:

```javascript
fetch(url).then(response => {{
    if (!response.ok) {{
        throw new Error(`HTTP error ${{response.status}}: ${{response.statusText}}` || "Failed to load diff");
    }}
    return response.json();  // First call to response.json()
}})
.then(response => {{
    if (!response.ok) {{
        throw new Error('Failed to load diff');
    }}
    return response.json();  // Second call to response.json() - ERROR!
}})
```

This caused the second `then()` handler to receive the already parsed JSON result from the first handler, not a Response object. Since the result doesn't have an `ok` property or a `json()` method, this caused the error.

### Solution

Removed the redundant second `then()` handler that was trying to process the Response object a second time:

```javascript
fetch(url).then(response => {{
    if (!response.ok) {{
        throw new Error(`HTTP error ${{response.status}}: ${{response.statusText}}` || "Failed to load diff");
    }}
    return response.json();  // Parse JSON only once
}})
.then(data => {{
    // Use the data directly
    // ...
}})
```

### Implementation Details

1. Created a backup of the original JavaScript file
2. Identified the problematic fetch chain
3. Removed the redundant `then()` handler
4. Fixed the Promise chain to properly handle the parsed JSON response

### Verification

The fix was verified by:
1. Comparing different versions of the ontology
2. Checking the JavaScript console for errors
3. Verifying the diff content loads correctly

This fix resolves the final issue with the diff viewer, allowing users to properly compare any two versions of an ontology.
"""
    
    # Read the current CLAUDE.md file
    try:
        with open('CLAUDE.md', 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading CLAUDE.md: {str(e)}")
        return False
    
    # Insert new content after the first line (title)
    lines = content.split('\n')
    if len(lines) >= 1:
        # If file has content, add after title
        new_full_content = lines[0] + "\n" + new_content + "\n" + "\n".join(lines[1:])
    else:
        # Empty file, just add content
        new_full_content = "# ProEthica Development Log\n" + new_content
    
    # Write the updated content back
    try:
        with open('CLAUDE.md', 'w') as f:
            f.write(new_full_content)
        print("Successfully updated CLAUDE.md")
        return True
    except Exception as e:
        print(f"Error writing to CLAUDE.md: {str(e)}")
        return False

if __name__ == "__main__":
    update_claude_md()
