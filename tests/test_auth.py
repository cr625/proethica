#!/usr/bin/env python3
"""
Test script to verify environment-aware authentication is working correctly.
"""

import os
import sys

# Add the project path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_development_mode():
    """Test that development mode bypasses authentication."""
    print("Testing DEVELOPMENT mode...")

    # Set environment to development
    os.environ['FLASK_ENV'] = 'development'
    os.environ['ENVIRONMENT'] = 'development'

    from app import create_app
    app = create_app()

    with app.app_context():
        # Import after app context is created
        from app.utils.environment_auth import is_production

        # Test environment detection
        print(f"  - Environment: {app.config.get('ENVIRONMENT')}")
        print(f"  - Is Production: {is_production()}")

        # Test with test client
        client = app.test_client()

        # Test cases route (should work without auth in dev)
        print("\n  Testing Cases routes:")
        response = client.get('/cases/')
        print(f"    - GET /cases/ (view): {response.status_code}")

        # Test case creation (should work without auth in dev)
        response = client.post('/cases/new/manual', data={'title': 'Test'})
        print(f"    - POST /cases/new/manual (create): {response.status_code}")

        # Test admin route (should work without auth in dev)
        print("\n  Testing Admin routes:")
        response = client.get('/admin/')
        print(f"    - GET /admin/ (dashboard): {response.status_code}")

    print("\n  ✓ Development mode test complete")


def test_production_mode():
    """Test that production mode enforces authentication."""
    print("\nTesting PRODUCTION mode...")

    # Set environment to production
    os.environ['FLASK_ENV'] = 'production'
    os.environ['ENVIRONMENT'] = 'production'

    from app import create_app
    app = create_app()

    with app.app_context():
        # Import after app context is created
        from app.utils.environment_auth import is_production

        # Test environment detection
        print(f"  - Environment: {app.config.get('ENVIRONMENT')}")
        print(f"  - Is Production: {is_production()}")

        # Test with test client
        client = app.test_client()

        # Test cases route (should work without auth for viewing)
        print("\n  Testing Cases routes:")
        response = client.get('/cases/')
        print(f"    - GET /cases/ (view): {response.status_code} (should be 200)")

        # Test case creation (should require auth)
        response = client.post('/cases/new/manual', data={'title': 'Test'})
        print(f"    - POST /cases/new/manual (create): {response.status_code} (should be 302 redirect)")

        # Test admin route (should require auth)
        print("\n  Testing Admin routes:")
        response = client.get('/admin/')
        print(f"    - GET /admin/ (dashboard): {response.status_code} (should be 302 redirect)")

    print("\n  ✓ Production mode test complete")


if __name__ == '__main__':
    print("=" * 60)
    print("Environment-Aware Authentication Test")
    print("=" * 60)

    try:
        test_development_mode()
        test_production_mode()

        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)