#!/usr/bin/env python3
"""
Script to download and verify required NLTK resources for the application.
This should be run during application setup or deployment.
"""
import nltk
import os
import sys

print("Setting up NLTK resources...")

# Define resources needed
resources = ['punkt', 'stopwords']

# Try to download each resource
success = True
for resource in resources:
    try:
        print(f"Checking/downloading NLTK resource: {resource}")
        nltk.download(resource)
        # Verify the resource is now available
        if resource == 'punkt':
            nltk.data.find('tokenizers/punkt')
        elif resource == 'stopwords':
            nltk.data.find('corpora/stopwords')
        print(f"✓ Successfully set up {resource}")
    except Exception as e:
        print(f"✗ Failed to set up {resource}: {str(e)}", file=sys.stderr)
        success = False

if not success:
    print("\nERROR: Failed to set up all required NLTK resources.", file=sys.stderr)
    print("Please ensure internet connectivity and try again.", file=sys.stderr)
    sys.exit(1)

print("\nAll NLTK resources successfully installed!")
