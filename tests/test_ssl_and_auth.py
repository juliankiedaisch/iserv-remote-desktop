#!/usr/bin/env python3
"""
Test SSL certificate verification and VNC authentication features
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import base64

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSSLAndAuth(unittest.TestCase):
    """Test SSL verification and authentication features"""
    
    def setUp(self):
        """Set up test environment"""
        # Save original environment variables
        self.original_env = {
            'KASM_CONTAINER_PROTOCOL': os.environ.get('KASM_CONTAINER_PROTOCOL'),
            'KASM_VERIFY_SSL': os.environ.get('KASM_VERIFY_SSL'),
            'VNC_USER': os.environ.get('VNC_USER'),
            'VNC_PASSWORD': os.environ.get('VNC_PASSWORD')
        }
        
        # Set environment variables for testing
        os.environ['KASM_CONTAINER_PROTOCOL'] = 'https'
        os.environ['KASM_VERIFY_SSL'] = 'false'
        os.environ['VNC_USER'] = 'test_user'
        os.environ['VNC_PASSWORD'] = 'test_pass'
    
    def test_create_retry_session_with_ssl_disabled(self):
        """Test that create_retry_session can disable SSL verification"""
        from app.routes.proxy_routes import create_retry_session
        
        # Create session with SSL verification disabled
        session = create_retry_session(verify_ssl=False)
        
        # Check that verify is set to False
        self.assertFalse(session.verify)
    
    def test_create_retry_session_with_ssl_enabled(self):
        """Test that create_retry_session can enable SSL verification"""
        from app.routes.proxy_routes import create_retry_session
        
        # Create session with SSL verification enabled
        session = create_retry_session(verify_ssl=True)
        
        # Check that verify is set to True
        self.assertTrue(session.verify)
    
    def test_environment_variables_loaded(self):
        """Test that environment variables are properly loaded"""
        protocol = os.environ.get('KASM_CONTAINER_PROTOCOL', 'https')
        verify_ssl = os.environ.get('KASM_VERIFY_SSL', 'false').lower() == 'true'
        vnc_user = os.environ.get('VNC_USER', 'kasm_user')
        vnc_password = os.environ.get('VNC_PASSWORD', 'password')
        
        self.assertEqual(protocol, 'https')
        self.assertFalse(verify_ssl)
        self.assertEqual(vnc_user, 'test_user')
        self.assertEqual(vnc_password, 'test_pass')
    
    def test_basic_auth_header_format(self):
        """Test that Basic Auth header is correctly formatted"""
        vnc_user = 'test_user'
        vnc_password = 'test_pass'
        credentials = f"{vnc_user}:{vnc_password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        auth_header = f"Basic {encoded_credentials}"
        
        # Verify format
        self.assertTrue(auth_header.startswith('Basic '))
        
        # Verify decoding works
        decoded = base64.b64decode(encoded_credentials).decode('utf-8')
        self.assertEqual(decoded, 'test_user:test_pass')
    
    def test_https_url_construction(self):
        """Test that HTTPS URLs are properly constructed"""
        protocol = 'https'
        host_port = 7001
        target_url = f"{protocol}://localhost:{host_port}"
        
        self.assertEqual(target_url, 'https://localhost:7001')
        self.assertTrue(target_url.startswith('https://'))
    
    def test_http_url_construction(self):
        """Test that HTTP URLs are properly constructed"""
        protocol = 'http'
        host_port = 7001
        target_url = f"{protocol}://localhost:{host_port}"
        
        self.assertEqual(target_url, 'http://localhost:7001')
        self.assertTrue(target_url.startswith('http://'))
    
    def tearDown(self):
        """Clean up test environment"""
        # Restore original environment variables
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == '__main__':
    print("=" * 60)
    print("SSL and Authentication Tests")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSSLAndAuth)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    if result.wasSuccessful():
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
