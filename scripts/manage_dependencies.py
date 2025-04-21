#!/usr/bin/env python3
"""
Dependency Management Script for AI Ethical DM

This script helps manage Python dependencies by installing only the packages needed
for specific features, reducing overhead from unnecessary dependencies (especially
heavy ones like CUDA-enabled packages).

Usage:
    python scripts/manage_dependencies.py install-core  # Install core dependencies only
    python scripts/manage_dependencies.py install-all   # Install all dependencies
    python scripts/manage_dependencies.py install-feature agent  # Install agent dependencies
    python scripts/manage_dependencies.py install-feature embedding  # Install embedding dependencies
    python scripts/manage_dependencies.py analyze       # Analyze which features are active
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Define dependency groups
CORE_DEPS = [
    "flask",
    "sqlalchemy",
    "flask-sqlalchemy",
    "flask-migrate",
    "flask-login",
    "flask-wtf",
    "python-dotenv",
    "werkzeug",
    "psycopg2-binary",
    "rdflib",
    "aiohttp",
    "requests",
    "gunicorn",
    # Development dependencies
    "pytest",
    "pytest-flask",
    "email_validator",
    "black",
    "flake8"
]

FEATURE_DEPS = {
    "agent": [
        "anthropic>=0.18.0",
        "langchain",
        "langchain-core",
        "langchain-anthropic",
        "langchain-community",
        "langgraph",
    ],
    "documents": [
        "PyPDF2",
        "python-docx",
        "beautifulsoup4",
    ],
    "embedding": [
        "pgvector",
        "sentence-transformers",
        "chromadb",
    ],
    "zotero": [
        "pyzotero",
    ],
    "mcp": [
        "mcp[cli]",
    ]
}

def load_env_vars(env_file='.env'):
    """Load environment variables from .env file"""
    env_vars = {}
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
        return env_vars
    except Exception as e:
        print(f"Error loading .env file: {e}")
        return {}

def detect_active_features():
    """Detect which features are active based on .env settings"""
    env_vars = load_env_vars()
    
    active_features = {}
    
    # Claude API integration
    active_features["agent"] = env_vars.get('USE_CLAUDE', 'true').lower() == 'true' or \
                              env_vars.get('USE_AGENT_ORCHESTRATOR', 'true').lower() == 'true'
    
    # Embedding features
    active_features["embedding"] = env_vars.get('EMBEDDING_PROVIDER_PRIORITY', '').lower() != ''
    
    # Zotero integration
    active_features["zotero"] = env_vars.get('ZOTERO_API_KEY', '') != '' and \
                               env_vars.get('ZOTERO_USER_ID', '') != ''
    
    # Document processing (always assume active as it's a core feature)
    active_features["documents"] = True
    
    # MCP CLI tools (assume not active by default)
    active_features["mcp"] = False
    
    return active_features

def install_dependencies(packages):
    """Install the specified packages using pip"""
    if not packages:
        print("No packages to install.")
        return
    
    cmd = [sys.executable, "-m", "pip", "install"] + packages
    print(f"Installing packages: {', '.join(packages)}")
    subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser(description="Manage dependencies for AI Ethical DM")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Install core dependencies
    subparsers.add_parser('install-core', help='Install only core dependencies')
    
    # Install all dependencies
    subparsers.add_parser('install-all', help='Install all dependencies')
    
    # Install feature-specific dependencies
    feature_parser = subparsers.add_parser('install-feature', help='Install dependencies for specific features')
    feature_parser.add_argument('feature', choices=list(FEATURE_DEPS.keys()) + ['all'],
                               help='Feature to install dependencies for')
    
    # Analyze active features
    subparsers.add_parser('analyze', help='Analyze which features are active')
    
    args = parser.parse_args()
    
    if args.command == 'install-core':
        install_dependencies(CORE_DEPS)
    
    elif args.command == 'install-all':
        all_deps = CORE_DEPS.copy()
        for feature_deps in FEATURE_DEPS.values():
            all_deps.extend(feature_deps)
        install_dependencies(all_deps)
    
    elif args.command == 'install-feature':
        if args.feature == 'all':
            for feature, deps in FEATURE_DEPS.items():
                print(f"\nInstalling {feature} dependencies:")
                install_dependencies(deps)
        else:
            install_dependencies(FEATURE_DEPS[args.feature])
    
    elif args.command == 'analyze':
        active_features = detect_active_features()
        print("\nActive Features Analysis:")
        print("------------------------")
        
        for feature, is_active in active_features.items():
            status = "ACTIVE" if is_active else "INACTIVE"
            print(f"{feature.upper()}: {status}")
            if is_active:
                print(f"  Required packages: {', '.join(FEATURE_DEPS[feature])}")
        
        print("\nRecommended Installation Commands:")
        print("-------------------------------")
        print("# Core dependencies (always required):")
        print("python scripts/manage_dependencies.py install-core")
        
        active_feature_names = [f for f, active in active_features.items() if active]
        if active_feature_names:
            print("\n# Feature-specific dependencies:")
            for feature in active_feature_names:
                print(f"python scripts/manage_dependencies.py install-feature {feature}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
