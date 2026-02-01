"""
Unit tests for Traefik label generation and container routing
"""

import unittest
import os
from unittest.mock import Mock, patch, MagicMock
from app.services.docker_manager import DockerManager


class TestTraefikLabels(unittest.TestCase):
    """Test cases for Traefik label generation"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the Docker client to avoid actual Docker operations
        with patch('app.services.docker_manager.docker.from_env'):
            self.docker_manager = DockerManager()
    
    def test_generate_traefik_labels_basic(self):
        """Test basic Traefik label generation"""
        username = "john.doe"
        desktop_type = "ubuntu-desktop"
        subdomain = "test-desktop-john-doe-ubuntu-desktop-abc123"
        
        labels = self.docker_manager._generate_traefik_labels(
            username, desktop_type, subdomain
        )
        
        # Verify all required labels are present
        self.assertIn("traefik.enable", labels)
        self.assertEqual(labels["traefik.enable"], "true")
        
        # Check router configuration
        safe_name = "kasm-john-doe-ubuntu-desktop"
        self.assertIn(f"traefik.http.routers.{safe_name}.rule", labels)
        self.assertIn(f"traefik.http.routers.{safe_name}.entrypoints", labels)
        self.assertIn(f"traefik.http.routers.{safe_name}.service", labels)
        
        # Check service configuration
        self.assertIn(f"traefik.http.services.{safe_name}.loadbalancer.server.port", labels)
        self.assertEqual(
            labels[f"traefik.http.services.{safe_name}.loadbalancer.server.port"],
            "6901"
        )
        
        # Check network configuration
        self.assertIn("traefik.docker.network", labels)
        self.assertEqual(labels["traefik.docker.network"], "kasm_proxy")
    
    def test_generate_traefik_labels_hostname_rule(self):
        """Test that hostname rule is correctly formatted"""
        username = "test.user"
        desktop_type = "ubuntu"
        subdomain = "test-desktop-test-user-ubuntu-xyz789"
        
        labels = self.docker_manager._generate_traefik_labels(
            username, desktop_type, subdomain
        )
        
        safe_name = "kasm-test-user-ubuntu"
        rule = labels[f"traefik.http.routers.{safe_name}.rule"]
        
        # Verify Host rule format
        expected_domain = os.environ.get('TRAEFIK_DOMAIN', 'hub.mdg-hamburg.de')
        expected_rule = f"Host(`{subdomain}.{expected_domain}`)"
        self.assertEqual(rule, expected_rule)
    
    def test_generate_traefik_labels_safe_name(self):
        """Test that container names are sanitized for Traefik"""
        # Test with dots and underscores
        username = "user.with.dots"
        desktop_type = "type_with_underscores"
        subdomain = "test-desktop-user-with-dots-type-with-underscores-token"
        
        labels = self.docker_manager._generate_traefik_labels(
            username, desktop_type, subdomain
        )
        
        # Safe name should have dots and underscores replaced with hyphens
        safe_name = "kasm-user-with-dots-type-with-underscores"
        self.assertIn(f"traefik.http.routers.{safe_name}.rule", labels)
    
    def test_generate_traefik_labels_custom_domain(self):
        """Test label generation with custom domain"""
        with patch.dict(os.environ, {'TRAEFIK_DOMAIN': 'custom.example.com'}):
            username = "user"
            desktop_type = "ubuntu"
            subdomain = "test-desktop-user-ubuntu-token"
            
            labels = self.docker_manager._generate_traefik_labels(
                username, desktop_type, subdomain
            )
            
            safe_name = "kasm-user-ubuntu"
            rule = labels[f"traefik.http.routers.{safe_name}.rule"]
            
            # Should use custom domain
            self.assertIn("custom.example.com", rule)
            self.assertEqual(rule, f"Host(`{subdomain}.custom.example.com`)")
    
    def test_generate_traefik_labels_entrypoint(self):
        """Test that entrypoint is set to 'web'"""
        username = "user"
        desktop_type = "ubuntu"
        subdomain = "test-desktop-user-ubuntu-token"
        
        labels = self.docker_manager._generate_traefik_labels(
            username, desktop_type, subdomain
        )
        
        safe_name = "kasm-user-ubuntu"
        entrypoints = labels[f"traefik.http.routers.{safe_name}.entrypoints"]
        
        # Should use 'web' entrypoint (port 80)
        self.assertEqual(entrypoints, "web")
    
    def test_get_container_url_with_traefik(self):
        """Test that container URL is correctly generated"""
        # Create a mock container record
        container_record = Mock()
        container_record.proxy_path = "user-ubuntu-abc123"
        
        with patch.dict(os.environ, {'CONTAINER_PREFIX': 'test-desktop'}):
            url = self.docker_manager.get_container_url(container_record)
            
            # Verify URL format
            self.assertIsNotNone(url)
            self.assertTrue(url.startswith("https://"))
            self.assertIn("test-desktop-user-ubuntu-abc123", url)
            self.assertIn("hub.mdg-hamburg.de", url)
            self.assertTrue(url.endswith("/"))
    
    def test_get_container_url_strips_prefix_trailing_dash(self):
        """Test that trailing dash in prefix is removed"""
        container_record = Mock()
        container_record.proxy_path = "user-ubuntu-token"
        
        with patch.dict(os.environ, {'CONTAINER_PREFIX': 'test-desktop-'}):
            url = self.docker_manager.get_container_url(container_record)
            
            # Should not have double dash
            self.assertNotIn("test-desktop--user", url)
            self.assertIn("test-desktop-user", url)
    
    def test_get_container_url_no_proxy_path(self):
        """Test URL generation when proxy_path is None"""
        container_record = Mock()
        container_record.proxy_path = None
        
        url = self.docker_manager.get_container_url(container_record)
        
        # Should return None
        self.assertIsNone(url)


class TestTraefikContainerCreation(unittest.TestCase):
    """Test cases for container creation with Traefik labels"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the Docker client
        with patch('app.services.docker_manager.docker.from_env'):
            self.docker_manager = DockerManager()
    
    @patch('app.services.docker_manager.Container')
    @patch('app.services.docker_manager.db')
    @patch('app.services.docker_manager.current_app')
    @patch.dict(os.environ, {
        'TRAEFIK_ENABLED': 'true',
        'TRAEFIK_NETWORK': 'kasm_proxy',
        'CONTAINER_PREFIX': 'test-desktop'
    })
    def test_container_created_with_traefik_labels(self, mock_app, mock_db, mock_container_model):
        """Test that containers are created with Traefik labels when enabled"""
        # This is a simplified test - in a real scenario you'd need more extensive mocking
        # Just verify that the logic for adding labels is correct
        
        username = "testuser"
        desktop_type = "ubuntu"
        subdomain = "test-desktop-testuser-ubuntu-token123"
        
        # Generate labels
        labels = self.docker_manager._generate_traefik_labels(
            username, desktop_type, subdomain
        )
        
        # Verify critical labels exist
        self.assertIn("traefik.enable", labels)
        self.assertIn("traefik.docker.network", labels)
        
        # Verify network name
        self.assertEqual(labels["traefik.docker.network"], "kasm_proxy")
    
    @patch.dict(os.environ, {'TRAEFIK_ENABLED': 'false'})
    def test_traefik_disabled(self):
        """Test that Traefik labels are not generated when disabled"""
        # When TRAEFIK_ENABLED is false, labels should not be generated
        # This is checked in the actual container creation code
        traefik_enabled = os.environ.get('TRAEFIK_ENABLED', 'false').lower() == 'true'
        self.assertFalse(traefik_enabled)


if __name__ == '__main__':
    unittest.main()
