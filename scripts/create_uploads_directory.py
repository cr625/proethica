#!/usr/bin/env python
"""
Script to create the uploads directory for storing uploaded documents.
"""

import os
import sys

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app

def create_uploads_directory():
    """Create the uploads directory for storing uploaded documents."""
    app = create_app()
    
    with app.app_context():
        # Configure upload folder
        UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'uploads')
        
        # Create the directory if it doesn't exist
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            print(f"Created uploads directory at: {UPLOAD_FOLDER}")
        else:
            print(f"Uploads directory already exists at: {UPLOAD_FOLDER}")
        
        # Create a .gitkeep file to ensure the directory is tracked by git
        gitkeep_path = os.path.join(UPLOAD_FOLDER, '.gitkeep')
        if not os.path.exists(gitkeep_path):
            with open(gitkeep_path, 'w') as f:
                f.write('# This file ensures the uploads directory is tracked by git\n')
            print("Created .gitkeep file")
        
        # Create a .gitignore file to ignore uploaded files
        gitignore_path = os.path.join(UPLOAD_FOLDER, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write('# Ignore all files in this directory\n')
                f.write('*\n')
                f.write('# Except for .gitkeep\n')
                f.write('!.gitkeep\n')
                f.write('!.gitignore\n')
            print("Created .gitignore file to ignore uploaded files")

if __name__ == "__main__":
    create_uploads_directory()
