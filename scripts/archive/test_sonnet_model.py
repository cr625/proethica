#!/usr/bin/env python3
"""
Test script to verify that we're using Claude Sonnet model in the
GuidelineAnalysisModule.
"""

import re
import sys
from pathlib import Path

# Get the file path
file_path = Path("mcp/modules/guideline_analysis_module.py")

# Read the current content
with open(file_path, "r") as f:
    content = f.read()

# Check for Claude Sonnet model string
if "claude-3-sonnet-20240229" in content:
    print("✅ File is already using Claude 3 Sonnet model")
    
    # Add model name comments if not present
    if "# Use Claude 3 Sonnet model" not in content:
        # Update the file with clearer model comments
        updated_content = content.replace(
            "if hasattr(self.llm_client, 'messages'):  # Anthropic Claude",
            "if hasattr(self.llm_client, 'messages'):  # Anthropic Claude\n                # Use Claude 3 Sonnet model",
            2  # Match both occurrences
        )
        
        # Only write if changed
        if updated_content != content:
            print("✏️ Adding explicit model comments for clarity")
            with open(file_path, "w") as f:
                f.write(updated_content)
            print("✅ File updated successfully")
        else:
            print("⚠️ No changes needed")
    else:
        print("✅ Comments about Claude 3 Sonnet already present")
else:
    print("❌ File is NOT using Claude 3 Sonnet model")
    print("Please update the model name to claude-3-sonnet-20240229")
