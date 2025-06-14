#!/usr/bin/env python3
"""Test script for the dashboard functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for testing
os.environ['BYPASS_AUTH'] = 'true'
os.environ['ENVIRONMENT'] = 'development'

from app import create_app
from app.routes.dashboard import get_system_statistics, get_workflow_status, assess_capabilities


def test_dashboard_data():
    """Test dashboard data collection functions."""
    print("=" * 60)
    print("Dashboard Data Test")
    print("=" * 60)
    
    # Create app context with config
    app = create_app('config')
    
    with app.app_context():
        print("\n1. Testing system statistics:")
        try:
            stats = get_system_statistics()
            print(f"   ✓ Overview: {stats['overview']}")
            print(f"   ✓ Processing rates: {stats['processing']['processing_rate']:.1f}% docs, {stats['processing']['embedding_rate']:.1f}% sections")
            print(f"   ✓ Analysis: {stats['analysis']['analyzed_guidelines']} guidelines analyzed")
        except Exception as e:
            print(f"   ✗ Error getting statistics: {e}")
        
        print("\n2. Testing workflow status:")
        try:
            workflow = get_workflow_status()
            print(f"   ✓ Pipeline has {len(workflow['pipeline'])} steps")
            print(f"   ✓ Overall completion: {workflow['overall_completion']:.1f}%")
            
            # Show pipeline status
            for step_name, step_info in workflow['pipeline'].items():
                status_icon = "✓" if step_info['status'] == 'operational' else "✗" if step_info['status'] == 'missing' else "⚠"
                print(f"     {status_icon} {step_info['name']}: {step_info['completion']}% ({step_info['status']})")
                
        except Exception as e:
            print(f"   ✗ Error getting workflow status: {e}")
        
        print("\n3. Testing capabilities assessment:")
        try:
            capabilities = assess_capabilities()
            print(f"   ✓ Found {len(capabilities)} capability areas")
            
            for cap_name, cap_info in capabilities.items():
                status_icon = "✓" if cap_info['status'] == 'excellent' else "⚠" if cap_info['status'] in ['good', 'needs_work'] else "✗"
                print(f"     {status_icon} {cap_info['name']}: {cap_info['completion']}% ({cap_info['status']})")
                
        except Exception as e:
            print(f"   ✗ Error getting capabilities: {e}")
    
    print("\n" + "=" * 60)
    print("Dashboard Data Test Complete")
    print("=" * 60)


def test_dashboard_routes():
    """Test dashboard route accessibility."""
    print("\n" + "=" * 60)
    print("Dashboard Routes Test")
    print("=" * 60)
    
    # Create app with test client
    app = create_app('config')
    
    with app.test_client() as client:
        routes_to_test = [
            ('/dashboard/', 'Main Dashboard'),
            ('/dashboard/api/stats', 'Stats API'),
            ('/dashboard/api/workflow', 'Workflow API'),
            ('/dashboard/api/capabilities', 'Capabilities API')
        ]
        
        for route, description in routes_to_test:
            try:
                response = client.get(route)
                if response.status_code == 200:
                    print(f"   ✓ {description} ({route}): OK")
                    if route.startswith('/dashboard/api/'):
                        # For API routes, check if we get JSON
                        try:
                            data = response.get_json()
                            print(f"     - JSON response with {len(data)} keys")
                        except:
                            print(f"     - Response length: {len(response.data)} bytes")
                else:
                    print(f"   ✗ {description} ({route}): HTTP {response.status_code}")
            except Exception as e:
                print(f"   ✗ {description} ({route}): Error - {e}")
    
    print("\n" + "=" * 60)
    print("Dashboard Routes Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    test_dashboard_data()
    test_dashboard_routes()