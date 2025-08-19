#!/usr/bin/env python3
"""Run ProEthica with dashboard for testing."""

import os
import sys
import subprocess
import time

# Set environment variables for development
os.environ['BYPASS_AUTH'] = 'true'
os.environ['ENVIRONMENT'] = 'development'
os.environ['DEBUG'] = 'true'

print("=" * 60)
print("Starting ProEthica with Dashboard")
print("=" * 60)

print("\n🌟 Dashboard Features:")
print("✅ System Overview - Shows worlds, guidelines, cases, documents")
print("✅ Pipeline Status - 8-step ethical decision-making workflow") 
print("✅ Capabilities Assessment - 8 capability areas with completion rates")
print("✅ Processing Statistics - Document processing and embedding rates")
print("✅ Recent Activity - Latest documents, guidelines, and worlds")
print("✅ Quick Actions - Links to create content and run analysis")

print("\n📊 Current System Status:")
print("• Overall Completion: 66.2%")
print("• 5 Components Operational (Document Import → Association Generation)")
print("• 2 Components Missing (Recommendation Engine, Outcome Tracking)")
print("• 1 Component Partial (Decision Visualization)")

print("\n🔗 URLs to visit:")
print("• Main Dashboard: http://localhost:3333/dashboard")
print("• Dashboard API (Stats): http://localhost:3333/dashboard/api/stats")
print("• Dashboard API (Workflow): http://localhost:3333/dashboard/api/workflow")
print("• Dashboard API (Capabilities): http://localhost:3333/dashboard/api/capabilities")
print("• World-specific Dashboard: http://localhost:3333/dashboard/world/1")

print("\n🚀 Starting application...")
print("=" * 60)

# Run the application
try:
    subprocess.run([sys.executable, "run.py", "--port", "3333"], check=True)
except KeyboardInterrupt:
    print("\n\n👋 Application stopped.")
except Exception as e:
    print(f"\n❌ Error starting application: {e}")