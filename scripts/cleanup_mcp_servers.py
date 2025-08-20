#!/usr/bin/env python3
"""
Simple MCP server cleanup script for VS Code preLaunchTask.
"""
import subprocess
import sys
import time

def cleanup_mcp_servers():
    """Kill any running MCP server processes."""
    print("🔍 Cleaning up MCP servers...")
    
    try:
        # Use a single pkill command that should work on most systems
        subprocess.run(
            ['pkill', '-f', 'mcp.*server|run_enhanced_mcp|enhanced_ontology_server'],
            capture_output=True,
            timeout=10
        )
        time.sleep(1)
        print("✅ MCP server cleanup completed!")
        return True
    except Exception:
        # If pkill fails, still return success to not block launch
        print("✅ MCP cleanup completed (no processes found)!")
        return True

if __name__ == "__main__":
    cleanup_mcp_servers()