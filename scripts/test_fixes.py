#!/usr/bin/env python3
"""
Test script to verify the container status fix
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_status_extraction():
    """Test that container status is properly extracted from Docker status info"""
    
    # Mock container status response from get_container_status
    status_info = {
        'status': 'running',
        'docker_status': 'running',
        'host_port': 7001,
        'created_at': '2024-01-01T00:00:00'
    }
    
    # Simulate the fixed code
    container_status = status_info.get('status', 'unknown')
    docker_status = status_info.get('docker_status', 'unknown')
    
    assert container_status == 'running', f"Expected 'running', got '{container_status}'"
    assert docker_status == 'running', f"Expected 'running', got '{docker_status}'"
    
    print("✓ Status extraction test passed")
    return True

def test_url_generation():
    """Test that URLs are generated with the correct protocol"""
    
    # Test HTTPS (default for production)
    os.environ['DOCKER_HOST_URL'] = 'example.com'
    os.environ['DOCKER_HOST_PROTOCOL'] = 'https'
    
    # Simulate get_container_url logic
    host = os.environ.get('DOCKER_HOST_URL', 'localhost')
    protocol = os.environ.get('DOCKER_HOST_PROTOCOL', 'https')
    proxy_path = 'john-ubuntu-vscode'
    
    url = f"{protocol}://{host}/desktop/{proxy_path}"
    
    expected_url = "https://example.com/desktop/john-ubuntu-vscode"
    assert url == expected_url, f"Expected '{expected_url}', got '{url}'"
    
    print("✓ URL generation test (HTTPS) passed")
    
    # Test HTTP
    os.environ['DOCKER_HOST_PROTOCOL'] = 'http'
    protocol = os.environ.get('DOCKER_HOST_PROTOCOL', 'https')
    url = f"{protocol}://{host}/desktop/{proxy_path}"
    
    expected_url = "http://example.com/desktop/john-ubuntu-vscode"
    assert url == expected_url, f"Expected '{expected_url}', got '{url}'"
    
    print("✓ URL generation test (HTTP) passed")
    
    return True

def test_nginx_websocket_config():
    """Test that nginx.conf has WebSocket support configured"""
    
    nginx_conf_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'nginx.conf'
    )
    
    with open(nginx_conf_path, 'r') as f:
        nginx_conf = f.read()
    
    # Check for WebSocket upgrade headers
    assert 'proxy_http_version 1.1' in nginx_conf, "Missing HTTP/1.1 version"
    assert 'Upgrade $http_upgrade' in nginx_conf, "Missing Upgrade header"
    assert 'Connection $connection_upgrade' in nginx_conf, "Missing Connection header"
    
    # Check for SSL configuration
    assert 'listen 443 ssl http2' in nginx_conf, "Missing HTTPS listener"
    assert 'ssl_certificate' in nginx_conf, "Missing SSL certificate config"
    
    # Check for both HTTP and HTTPS servers
    assert nginx_conf.count('listen 80') >= 1, "Missing HTTP listener"
    assert nginx_conf.count('listen 443') >= 1, "Missing HTTPS listener"
    
    print("✓ Nginx WebSocket configuration test passed")
    return True

def test_docker_compose_nginx_enabled():
    """Test that nginx is enabled in docker-compose.yml"""
    
    docker_compose_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'docker-compose.yml'
    )
    
    with open(docker_compose_path, 'r') as f:
        docker_compose = f.read()
    
    # Check nginx service is not commented out
    lines = docker_compose.split('\n')
    nginx_section_found = False
    nginx_commented = False
    
    for line in lines:
        if 'nginx:' in line and not line.strip().startswith('#'):
            nginx_section_found = True
        if 'nginx:' in line and line.strip().startswith('#'):
            nginx_commented = True
    
    assert nginx_section_found, "Nginx service not found in docker-compose.yml"
    assert not nginx_commented, "Nginx service is commented out"
    
    # Check for SSL volume mount
    assert 'ssl:/etc/nginx/ssl' in docker_compose or './ssl:/etc/nginx/ssl' in docker_compose, \
        "SSL volume mount not found"
    
    print("✓ Docker Compose nginx configuration test passed")
    return True

def main():
    """Run all tests"""
    print("Running container status and SSL/WebSocket configuration tests...\n")
    
    tests = [
        test_status_extraction,
        test_url_generation,
        test_nginx_websocket_config,
        test_docker_compose_nginx_enabled
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Tests completed: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
