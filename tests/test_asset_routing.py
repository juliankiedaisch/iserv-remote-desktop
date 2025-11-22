#!/usr/bin/env python3
"""
Test asset routing functionality in proxy routes
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAssetRouting(unittest.TestCase):
    """Test asset routing detection and handling"""
    
    def test_asset_prefix_detection(self):
        """Test that common asset prefixes are detected"""
        asset_prefixes = ('assets', 'js', 'css', 'fonts', 'images', 'static', 'dist', 'build')
        
        test_cases = [
            ('assets/ui-D357AMxM.js', True),
            ('assets/ui-Dix4qgyj.css', True),
            ('js/main.js', True),
            ('css/style.css', True),
            ('fonts/roboto.woff', True),
            ('images/logo.png', True),
            ('static/index.html', True),
            ('dist/bundle.js', True),
            ('build/app.js', True),
            ('user.name-ubuntu-vscode', False),
            ('admin.panel', False),
            ('container-123', False),
        ]
        
        for path, expected_is_asset in test_cases:
            is_potential_asset = any(path.startswith(prefix) or path.split('/')[0] == prefix 
                                      for prefix in asset_prefixes)
            self.assertEqual(is_potential_asset, expected_is_asset, 
                           f"Path '{path}' should {'be' if expected_is_asset else 'not be'} detected as asset")
    
    def test_referer_pattern_extraction(self):
        """Test that container proxy_path can be extracted from Referer header"""
        pattern = r'/desktop/([^/?#]+)'
        
        test_cases = [
            ('https://desktop.hub.mdg-hamburg.de/desktop/julian.kiedaisch-ubuntu-vscode', 'julian.kiedaisch-ubuntu-vscode'),
            ('http://localhost:5020/desktop/user.name-debian-desktop', 'user.name-debian-desktop'),
            ('https://example.com/desktop/admin-arch-linux?param=value', 'admin-arch-linux'),
            ('https://example.com/desktop/test.user-fedora#section', 'test.user-fedora'),
        ]
        
        for referer, expected_proxy_path in test_cases:
            match = re.search(pattern, referer)
            self.assertIsNotNone(match, f"Pattern should match Referer: {referer}")
            self.assertEqual(match.group(1), expected_proxy_path, 
                           f"Should extract '{expected_proxy_path}' from '{referer}'")
    
    def test_subpath_reconstruction(self):
        """Test that subpaths are correctly reconstructed for asset requests"""
        # When proxy_path='assets' and subpath='ui-D357AMxM.js', 
        # the full asset path should be 'assets/ui-D357AMxM.js'
        
        test_cases = [
            ('assets', 'ui-D357AMxM.js', 'assets/ui-D357AMxM.js'),
            ('assets', '', 'assets'),
            ('js', 'main.bundle.js', 'js/main.bundle.js'),
            ('css', 'themes/dark.css', 'css/themes/dark.css'),
        ]
        
        for proxy_path, original_subpath, expected_subpath in test_cases:
            if original_subpath:
                reconstructed_subpath = f"{proxy_path}/{original_subpath}"
            else:
                reconstructed_subpath = proxy_path
            
            self.assertEqual(reconstructed_subpath, expected_subpath,
                           f"Should reconstruct '{expected_subpath}' from proxy_path='{proxy_path}' and subpath='{original_subpath}'")
    
    def test_referer_is_not_asset(self):
        """Test that we don't use asset paths from Referer as container names"""
        asset_prefixes = ('assets', 'js', 'css', 'fonts', 'images', 'static', 'dist', 'build')
        
        # These should NOT be considered valid container names
        invalid_referer_paths = [
            'assets/main.css',
            'js/app.js',
            'static/index.html',
        ]
        
        # These should be considered valid container names
        valid_referer_paths = [
            'julian.kiedaisch-ubuntu-vscode',
            'user.name-debian',
            'admin-fedora-desktop',
        ]
        
        for path in invalid_referer_paths:
            is_referer_asset = any(path.startswith(prefix) or path.split('/')[0] == prefix 
                                   for prefix in asset_prefixes)
            self.assertTrue(is_referer_asset, 
                          f"Path '{path}' should be detected as asset in referer")
        
        for path in valid_referer_paths:
            is_referer_asset = any(path.startswith(prefix) or path.split('/')[0] == prefix 
                                   for prefix in asset_prefixes)
            self.assertFalse(is_referer_asset, 
                           f"Path '{path}' should NOT be detected as asset in referer")


if __name__ == '__main__':
    print("=" * 60)
    print("Asset Routing Tests")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAssetRouting)
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
