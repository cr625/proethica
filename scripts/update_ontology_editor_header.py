#!/usr/bin/env python3
"""
Update the ontology editor header to match the main application style
while maintaining modularity.
"""
import os
import re
from datetime import datetime

# Create backup of the original file
src_path = 'ontology_editor/templates/editor.html'
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

# Define the old navbar section to replace
old_navbar = r"""<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="{{ url_for\('ontology_editor.index'\) }}">BFO Ontology Editor</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link active" href="{{ url_for\('ontology_editor.index'\) }}">Editor</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>"""

# Define the new header section with similar style to the main app
new_header = r"""<div class="header">
        <nav class="navbar navbar-expand-lg navbar-light">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('ontology_editor.index') }}">ProEthica Ontology</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav me-auto">
                        <li class="nav-item">
                            <a class="nav-link active" href="{{ url_for('ontology_editor.index') }}">Editor</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/">Main Application</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    </div>"""

# Add CSS styles to the head section
head_styles = """
    <style>
        .header {
            padding-bottom: 20px;
            border-bottom: 1px solid #e5e5e5;
            margin-bottom: 30px;
        }
    </style>"""

# Replace the navbar with the new header
content = re.sub(old_navbar, new_header, content)

# Add header styles to the head section
content = content.replace('</head>', f'{head_styles}\n</head>')

# Update the file
with open(src_path, 'w') as f:
    f.write(content)

print(f"Updated {src_path} with new header styling to match main application")
