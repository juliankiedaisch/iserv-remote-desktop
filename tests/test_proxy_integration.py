#!/usr/bin/env python3
"""
Integration test for proxy routes with session tracking
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routes.proxy_routes import is_asset_path, ASSET_PREFIXES

class TestProxyIntegration(unittest.TestCase):
    """Integration tests for proxy routing with session tracking"""
    
    def setUp(self):
        """Set up test Flask app"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test_secret_key'
        self.app.config['SESSION_TYPE'] = 'filesystem'
        
    def test_asset_prefixes_include_app(self):
        """Test that 'app' is included in ASSET_PREFIXES"""
        self.assertIn('app', ASSET_PREFIXES, 
                     "ASSET_PREFIXES should include 'app' for Kasm app files")
    
    def test_app_path_detected_as_asset(self):
        """Test that app/* paths are detected as assets"""
        self.assertTrue(is_asset_path('app/locale/de.json'),
                       "app/locale/de.json should be detected as asset")
        self.assertTrue(is_asset_path('app'),
                       "app should be detected as asset prefix")
    
    def test_nested_asset_paths(self):
        """Test detection of various asset paths"""
        test_cases = [
            ('assets/ui.css', True),
            ('assets/fonts/font.woff', True),
            ('app/locale/de.json', True),
            ('js/main.js', True),
            ('package.json', True),
            ('user.name-ubuntu-vscode', False),
            ('julian.kiedaisch-ubuntu-vscode', False),
        ]
        
        for path, expected_is_asset in test_cases:
            result = is_asset_path(path)
            self.assertEqual(result, expected_is_asset,
                           f"Path '{path}' should {'be' if expected_is_asset else 'not be'} detected as asset")
    
    def test_font_file_detection(self):
        """Test that font files are detected as assets"""
        font_files = [
            'Orbitron700-DI3tXiXq.woff',
            'Orbitron700-CZNJeYVv.ttf',
            'font.woff2',
            'font.eot',
        ]
        
        for font_file in font_files:
            self.assertTrue(is_asset_path(font_file),
                          f"Font file '{font_file}' should be detected as asset")
    
    def test_audio_file_detection(self):
        """Test that audio files are detected as assets"""
        audio_files = [
            'bell-BmA9-LrF.oga',
            'notification.mp3',
            'alert.wav',
        ]
        
        for audio_file in audio_files:
            self.assertTrue(is_asset_path(audio_file),
                          f"Audio file '{audio_file}' should be detected as asset")

if __name__ == '__main__':
    print("=" * 60)
    print("Proxy Integration Tests")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestProxyIntegration)
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
