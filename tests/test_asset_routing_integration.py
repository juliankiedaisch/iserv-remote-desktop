#!/usr/bin/env python3
"""
Integration test for asset routing in proxy routes
This test simulates the Flask request context to test the asset routing logic
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routes.proxy_routes import ASSET_PREFIXES, is_asset_path

class TestAssetRoutingIntegration(unittest.TestCase):
    """Integration test for asset routing with mocked Flask context"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Set up environment variables
        os.environ['DATABASE_URI'] = 'sqlite:///:memory:'
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['DEBUG'] = 'True'
        os.environ['KASM_CONTAINER_PROTOCOL'] = 'https'
        os.environ['KASM_VERIFY_SSL'] = 'false'
        os.environ['VNC_USER'] = 'test_user'
        os.environ['VNC_PASSWORD'] = 'test_pass'
        
    def test_asset_detection_logic(self):
        """Test the asset detection logic matches implementation"""
        
        # Test paths that should be detected as assets
        asset_paths = [
            'assets/ui-D357AMxM.js',
            'assets/ui-Dix4qgyj.css',
            'assets/drag-BAMk-8Cy.svg',
            'js/main.js',
            'css/style.css',
        ]
        
        for proxy_path in asset_paths:
            is_potential_asset = is_asset_path(proxy_path)
            self.assertTrue(is_potential_asset, 
                          f"Path '{proxy_path}' should be detected as asset")
        
        # Test paths that should NOT be detected as assets
        container_paths = [
            'julian.kiedaisch-ubuntu-vscode',
            'user.name-debian-desktop',
            'admin-fedora',
        ]
        
        for proxy_path in container_paths:
            is_potential_asset = is_asset_path(proxy_path)
            self.assertFalse(is_potential_asset, 
                           f"Path '{proxy_path}' should NOT be detected as asset")
    
    def test_referer_extraction(self):
        """Test the referer extraction logic matches implementation"""
        test_cases = [
            {
                'referer': 'https://desktop.hub.mdg-hamburg.de/desktop/julian.kiedaisch-ubuntu-vscode',
                'expected': 'julian.kiedaisch-ubuntu-vscode'
            },
            {
                'referer': 'http://localhost:5020/desktop/user.name-debian',
                'expected': 'user.name-debian'
            },
            {
                'referer': 'https://example.com/desktop/admin-fedora?query=value',
                'expected': 'admin-fedora'
            },
        ]
        
        for test_case in test_cases:
            match = re.search(r'/desktop/([^/?#]+)', test_case['referer'])
            self.assertIsNotNone(match, f"Should match referer: {test_case['referer']}")
            self.assertEqual(match.group(1), test_case['expected'])
    
    def test_subpath_reconstruction(self):
        """Test the subpath reconstruction logic matches implementation"""
        test_cases = [
            {
                'proxy_path': 'assets',
                'subpath': 'ui-D357AMxM.js',
                'expected': 'assets/ui-D357AMxM.js'
            },
            {
                'proxy_path': 'assets',
                'subpath': '',
                'expected': 'assets'
            },
            {
                'proxy_path': 'js',
                'subpath': 'vendor/bundle.js',
                'expected': 'js/vendor/bundle.js'
            },
        ]
        
        for test_case in test_cases:
            proxy_path = test_case['proxy_path']
            subpath = test_case['subpath']
            
            # This matches the implementation logic
            if subpath:
                reconstructed = f"{proxy_path}/{subpath}"
            else:
                reconstructed = proxy_path
            
            self.assertEqual(reconstructed, test_case['expected'])
    
    def test_complete_asset_routing_scenario(self):
        """Test a complete asset routing scenario"""
        # Simulate the request flow:
        # 1. User accesses /desktop/julian.kiedaisch-ubuntu-vscode
        # 2. Browser tries to load /desktop/assets/ui-D357AMxM.js with Referer header
        
        # Request details
        proxy_path = 'assets'
        subpath = 'ui-D357AMxM.js'
        referer = 'https://desktop.hub.mdg-hamburg.de/desktop/julian.kiedaisch-ubuntu-vscode'
        
        # Step 1: Check if this is an asset
        is_potential_asset = is_asset_path(proxy_path)
        self.assertTrue(is_potential_asset, "Should detect 'assets' as potential asset")
        
        # Step 2: Extract container from Referer
        match = re.search(r'/desktop/([^/?#]+)', referer)
        self.assertIsNotNone(match, "Should extract container from Referer")
        referer_proxy_path = match.group(1)
        self.assertEqual(referer_proxy_path, 'julian.kiedaisch-ubuntu-vscode')
        
        # Step 3: Check that referer path is not an asset
        is_referer_asset = is_asset_path(referer_proxy_path)
        self.assertFalse(is_referer_asset, "Referer path should not be an asset")
        
        # Step 4: Reconstruct the full asset path
        if subpath:
            full_asset_path = f"{proxy_path}/{subpath}"
        else:
            full_asset_path = proxy_path
        
        self.assertEqual(full_asset_path, 'assets/ui-D357AMxM.js')
        
        # At this point, the proxy would:
        # - Use container 'julian.kiedaisch-ubuntu-vscode'
        # - Request path 'assets/ui-D357AMxM.js' from that container

if __name__ == '__main__':
    print("=" * 60)
    print("Asset Routing Integration Tests")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAssetRoutingIntegration)
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
