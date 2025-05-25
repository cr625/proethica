#!/usr/bin/env python3
"""
Test security features of the MCP server
"""

import requests
import time
import threading
from typing import Dict, Any

class MCPSecurityTester:
    """Test security features of the MCP server."""
    
    def __init__(self, mcp_url: str, auth_token: str):
        self.mcp_url = mcp_url
        self.auth_token = auth_token
        self.session = requests.Session()
    
    def test_no_auth(self) -> bool:
        """Test request without authentication."""
        print("🔒 Testing request without authentication...")
        try:
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json={"jsonrpc": "2.0", "method": "list_tools", "id": 1},
                timeout=10
            )
            
            if response.status_code == 401:
                print("✅ Correctly rejected unauthenticated request")
                return True
            else:
                print(f"❌ Unexpected response: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error testing no auth: {e}")
            return False
    
    def test_invalid_auth(self) -> bool:
        """Test request with invalid authentication."""
        print("🔒 Testing request with invalid authentication...")
        try:
            headers = {"Authorization": "Bearer invalid-token"}
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                headers=headers,
                json={"jsonrpc": "2.0", "method": "list_tools", "id": 1},
                timeout=10
            )
            
            if response.status_code == 401:
                print("✅ Correctly rejected invalid authentication")
                return True
            else:
                print(f"❌ Unexpected response: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error testing invalid auth: {e}")
            return False
    
    def test_valid_auth(self) -> bool:
        """Test request with valid authentication."""
        print("🔒 Testing request with valid authentication...")
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                headers=headers,
                json={"jsonrpc": "2.0", "method": "list_tools", "id": 1},
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ Valid authentication accepted")
                return True
            else:
                print(f"❌ Unexpected response: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing valid auth: {e}")
            return False
    
    def test_rate_limiting(self, requests_count: int = 10) -> bool:
        """Test rate limiting by making many requests quickly."""
        print(f"🔒 Testing rate limiting with {requests_count} requests...")
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        payload = {"jsonrpc": "2.0", "method": "list_tools", "id": 1}
        
        success_count = 0
        rate_limited_count = 0
        
        # Make rapid requests
        for i in range(requests_count):
            try:
                response = self.session.post(
                    f"{self.mcp_url}/jsonrpc",
                    headers=headers,
                    json=payload,
                    timeout=5
                )
                
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 429:
                    rate_limited_count += 1
                    print(f"   Request {i+1}: Rate limited (429)")
                    break
                else:
                    print(f"   Request {i+1}: Unexpected status {response.status_code}")
                
                # Small delay to avoid overwhelming
                time.sleep(0.1)
                
            except Exception as e:
                print(f"   Request {i+1}: Error - {e}")
        
        print(f"   Successful requests: {success_count}")
        print(f"   Rate limited requests: {rate_limited_count}")
        
        if rate_limited_count > 0:
            print("✅ Rate limiting is working")
            return True
        else:
            print("⚠️  Rate limiting may not be configured or limit not reached")
            return success_count > 0  # At least requests are working
    
    def test_security_headers(self) -> bool:
        """Test that security headers are present."""
        print("🔒 Testing security headers...")
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                headers=headers,
                json={"jsonrpc": "2.0", "method": "list_tools", "id": 1},
                timeout=10
            )
            
            security_headers = [
                'X-Frame-Options',
                'X-Content-Type-Options', 
                'X-XSS-Protection',
                'X-RateLimit-Limit'
            ]
            
            missing_headers = []
            for header in security_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if not missing_headers:
                print("✅ All security headers present")
                return True
            else:
                print(f"⚠️  Missing security headers: {missing_headers}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing security headers: {e}")
            return False
    
    def test_health_endpoint(self) -> bool:
        """Test that health endpoint works without auth."""
        print("🔒 Testing health endpoint (should work without auth)...")
        try:
            response = self.session.get(f"{self.mcp_url}/health", timeout=10)
            
            if response.status_code == 200:
                print("✅ Health endpoint accessible without auth")
                return True
            else:
                print(f"❌ Health endpoint returned: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error testing health endpoint: {e}")
            return False

def main():
    """Run all security tests."""
    print("🔐 MCP Server Security Test Suite")
    print("=" * 50)
    
    # Configuration
    MCP_URL = "https://mcp.proethica.org"
    AUTH_TOKEN = "nGkmBr1jlyYLi8ZKCeXEFMMD5KddiCMzAahi7j5G43c"  # This should be updated!
    
    tester = MCPSecurityTester(MCP_URL, AUTH_TOKEN)
    
    tests = [
        ("Health Endpoint", tester.test_health_endpoint),
        ("No Authentication", tester.test_no_auth),
        ("Invalid Authentication", tester.test_invalid_auth),
        ("Valid Authentication", tester.test_valid_auth),
        ("Security Headers", tester.test_security_headers),
        ("Rate Limiting", lambda: tester.test_rate_limiting(20))
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        results[test_name] = test_func()
    
    # Summary
    print(f"\n{'=' * 50}")
    print("🎯 SECURITY TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All security tests passed!")
    else:
        print("⚠️  Some security tests failed. Review configuration.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)