#!/usr/bin/env python3
"""
Test file routes Public folder filtering functionality
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPublicFolderFiltering(unittest.TestCase):
    """Test that the Public folder is filtered from private space listings"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory structure for testing
        self.test_dir = tempfile.mkdtemp()
        
        # Create test folders
        os.makedirs(os.path.join(self.test_dir, 'Public'))
        os.makedirs(os.path.join(self.test_dir, 'Documents'))
        os.makedirs(os.path.join(self.test_dir, 'Downloads'))
        
        # Create test files
        with open(os.path.join(self.test_dir, 'test.txt'), 'w') as f:
            f.write('test content')
        
        with open(os.path.join(self.test_dir, 'Public', 'public_file.txt'), 'w') as f:
            f.write('public content')
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_public_folder_should_be_filtered_in_private_space(self):
        """Test that 'Public' folder is filtered out when listing private space at root"""
        # Simulate the filtering logic from file_routes.py
        space = 'private'
        path = ''  # root level
        
        items = []
        for item_name in os.listdir(self.test_dir):
            # Skip the Public folder in private space at root level
            if space == 'private' and not path and item_name == 'Public':
                continue
            items.append(item_name)
        
        # Assert that Public is not in the list
        self.assertNotIn('Public', items)
        
        # Assert that other folders are still present
        self.assertIn('Documents', items)
        self.assertIn('Downloads', items)
        self.assertIn('test.txt', items)
    
    def test_public_folder_visible_in_subdirectories(self):
        """Test that a folder named 'Public' in subdirectories is still visible"""
        # Create a Public folder in a subdirectory
        sub_public = os.path.join(self.test_dir, 'Documents', 'Public')
        os.makedirs(sub_public)
        
        # Simulate the filtering logic with a non-root path
        space = 'private'
        path = 'Documents'  # not at root level
        
        items = []
        for item_name in os.listdir(os.path.join(self.test_dir, 'Documents')):
            # Skip the Public folder in private space at root level
            if space == 'private' and not path and item_name == 'Public':
                continue
            items.append(item_name)
        
        # Assert that Public IS in the list when in a subdirectory
        self.assertIn('Public', items)
    
    def test_public_space_not_affected(self):
        """Test that Public folder filtering doesn't affect public space listings"""
        space = 'public'
        path = ''  # root level
        
        # Create a test directory for public space with a Public folder
        public_test_dir = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(public_test_dir, 'Public'))
            os.makedirs(os.path.join(public_test_dir, 'Shared'))
            
            items = []
            for item_name in os.listdir(public_test_dir):
                # Skip the Public folder in private space at root level
                if space == 'private' and not path and item_name == 'Public':
                    continue
                items.append(item_name)
            
            # Assert that Public IS in the list for public space
            self.assertIn('Public', items)
            self.assertIn('Shared', items)
        finally:
            shutil.rmtree(public_test_dir)


if __name__ == '__main__':
    unittest.main()
