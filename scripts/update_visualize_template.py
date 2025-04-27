#!/usr/bin/env python3
"""
Update the ontology visualization template to match the main application style
while maintaining modularity.
"""
import os
import re
from datetime import datetime

# Create backup of the original file
src_path = 'ontology_editor/templates/visualize.html'
backup_path = f'{src_path}.header.bak'

# Create backup if it doesn't exist
if not os.path.exists(backup_path):
    with open(src_path, 'r') as f:
        content = f.read()
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"Created backup at {backup_path}")

# Read the file content
with open(src_path, 'r') as f:
    content = f.read()

# Update the title
content = content.replace('<title>Ontology Visualization</title>', 
                         '<title>ProEthica Ontology Visualization</title>')

# Add header styles to match the main application
# Define the CSS to add
header_styles = """
    /* Header and navbar styles to match main application */
    .header {
        padding-bottom: 20px;
        border-bottom: 1px solid #e5e5e5;
        margin-bottom: 30px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .navbar {
        width: 100%;
        padding: 0;
    }
    
    .navbar-light {
        background-color: transparent;
    }
"""

# Find where to add the header styles
style_tag_end = content.find('</style>')
if style_tag_end > -1:
    # Add the header styles to the existing style tag
    content = content[:style_tag_end] + header_styles + content[style_tag_end:]

# Find the body tag and replace the sidebar with a header
sidebar_pattern = r'<div class="sidebar">.*?</div>\s*<div class="main-content">'
sidebar_match = re.search(sidebar_pattern, content, re.DOTALL)

# Create the header HTML with the ProEthica style
header_html = """<div class="header">
        <nav class="navbar navbar-expand-lg navbar-light">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('ontology_editor.index') }}">ProEthica Ontology</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav me-auto">
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('ontology_editor.index') }}">Editor</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link active" href="#">Visualization</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/">Main Application</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    </div>
    <div class="main-content">\n"""

# Replace the beginning of the body with our new header structure
body_start = content.find('<body>')
container_start = content.find('<div class="container">', body_start)

if body_start > -1 and container_start > -1:
    # Replace the container div with our new structure
    new_content = content[:body_start + 7] + "\n" + header_html + content[container_start + 20:]
    content = new_content

# Update the file
with open(src_path, 'w') as f:
    f.write(content)

print(f"Updated {src_path} with new header styling to match main application")
