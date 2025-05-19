#!/usr/bin/env python3
"""
A simple script to test that necessary imports are working correctly.
"""
import sys
import os

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

# Try importing the module that was previously causing issues
print("\nTesting imports:")
try:
    import langchain_core
    print(f"✅ Successfully imported langchain_core (version: {langchain_core.__version__})")
except ImportError as e:
    print(f"❌ Failed to import langchain_core: {e}")

# Test some other critical imports
try:
    import langchain
    print(f"✅ Successfully imported langchain (version: {langchain.__version__})")
except ImportError as e:
    print(f"❌ Failed to import langchain: {e}")

try:
    import flask
    print(f"✅ Successfully imported flask (version: {flask.__version__})")
except ImportError as e:
    print(f"❌ Failed to import flask: {e}")

try:
    import anthropic
    print(f"✅ Successfully imported anthropic (version: {anthropic.__version__})")
except ImportError as e:
    print(f"❌ Failed to import anthropic: {e}")

print("\nEnvironment variables:")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
print(f"USE_CONDA: {os.environ.get('USE_CONDA', 'Not set')}")
