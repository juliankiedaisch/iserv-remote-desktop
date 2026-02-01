#!/usr/bin/env python3
"""
Standalone test script for Traefik label generation logic
This script tests the label generation without requiring full Flask setup
"""

import os
import sys


def generate_traefik_labels(username, desktop_type, subdomain):
    """
    Generate Traefik labels for automatic container routing
    (Standalone version for testing)
    """
    # Create a safe service name for Traefik labels
    label_base = f"kasm_{username}_{desktop_type}"
    safe_name = label_base.replace('.', '-').replace('_', '-')
    
    # Get domain from environment
    domain = os.environ.get('TRAEFIK_DOMAIN', 'hub.mdg-hamburg.de')
    full_domain = f"{subdomain}.{domain}"
    
    return {
        "traefik.enable": "true",
        f"traefik.http.routers.{safe_name}.rule": f"Host(`{full_domain}`)",
        f"traefik.http.routers.{safe_name}.entrypoints": "web",
        f"traefik.http.routers.{safe_name}.service": safe_name,
        f"traefik.http.services.{safe_name}.loadbalancer.server.port": "6901",
        "traefik.docker.network": "kasm_proxy",
    }


def test_label_generation():
    """Test basic label generation"""
    print("Test 1: Basic label generation")
    username = "john.doe"
    desktop_type = "ubuntu-desktop"
    subdomain = "test-desktop-john-doe-ubuntu-desktop-abc123"
    
    labels = generate_traefik_labels(username, desktop_type, subdomain)
    
    # Verify required labels
    assert "traefik.enable" in labels, "Missing traefik.enable label"
    assert labels["traefik.enable"] == "true", "traefik.enable should be 'true'"
    
    safe_name = "kasm-john-doe-ubuntu-desktop"
    assert f"traefik.http.routers.{safe_name}.rule" in labels, f"Missing router rule for {safe_name}"
    assert f"traefik.http.services.{safe_name}.loadbalancer.server.port" in labels, "Missing service port"
    assert labels[f"traefik.http.services.{safe_name}.loadbalancer.server.port"] == "6901", "Port should be 6901"
    assert labels["traefik.docker.network"] == "kasm_proxy", "Network should be kasm_proxy"
    
    print("✓ Basic label generation passed")


def test_hostname_rule():
    """Test hostname rule formatting"""
    print("\nTest 2: Hostname rule formatting")
    username = "test.user"
    desktop_type = "ubuntu"
    subdomain = "test-desktop-test-user-ubuntu-xyz789"
    
    labels = generate_traefik_labels(username, desktop_type, subdomain)
    
    safe_name = "kasm-test-user-ubuntu"
    rule = labels[f"traefik.http.routers.{safe_name}.rule"]
    
    expected_rule = f"Host(`{subdomain}.hub.mdg-hamburg.de`)"
    assert rule == expected_rule, f"Expected {expected_rule}, got {rule}"
    
    print("✓ Hostname rule formatting passed")


def test_safe_name_sanitization():
    """Test that names are sanitized"""
    print("\nTest 3: Safe name sanitization")
    username = "user.with.dots"
    desktop_type = "type_with_underscores"
    subdomain = "test-desktop-user-with-dots-type-with-underscores-token"
    
    labels = generate_traefik_labels(username, desktop_type, subdomain)
    
    safe_name = "kasm-user-with-dots-type-with-underscores"
    assert f"traefik.http.routers.{safe_name}.rule" in labels, "Safe name not properly sanitized"
    
    print("✓ Safe name sanitization passed")


def test_custom_domain():
    """Test with custom domain"""
    print("\nTest 4: Custom domain support")
    os.environ['TRAEFIK_DOMAIN'] = 'custom.example.com'
    
    username = "user"
    desktop_type = "ubuntu"
    subdomain = "test-desktop-user-ubuntu-token"
    
    labels = generate_traefik_labels(username, desktop_type, subdomain)
    
    safe_name = "kasm-user-ubuntu"
    rule = labels[f"traefik.http.routers.{safe_name}.rule"]
    
    assert "custom.example.com" in rule, "Custom domain not used"
    assert rule == f"Host(`{subdomain}.custom.example.com`)", "Custom domain rule incorrect"
    
    # Clean up
    del os.environ['TRAEFIK_DOMAIN']
    
    print("✓ Custom domain support passed")


def test_entrypoint():
    """Test entrypoint configuration"""
    print("\nTest 5: Entrypoint configuration")
    username = "user"
    desktop_type = "ubuntu"
    subdomain = "test-desktop-user-ubuntu-token"
    
    labels = generate_traefik_labels(username, desktop_type, subdomain)
    
    safe_name = "kasm-user-ubuntu"
    entrypoints = labels[f"traefik.http.routers.{safe_name}.entrypoints"]
    
    assert entrypoints == "web", f"Expected 'web' entrypoint, got {entrypoints}"
    
    print("✓ Entrypoint configuration passed")


def test_url_generation():
    """Test URL generation logic"""
    print("\nTest 6: URL generation")
    
    proxy_path = "user-ubuntu-abc123"
    prefix = os.environ.get('CONTAINER_PREFIX', 'test-desktop').rstrip('-')
    
    url = f"https://{prefix}-{proxy_path}.hub.mdg-hamburg.de/"
    
    assert url.startswith("https://"), "URL should start with https://"
    assert "test-desktop-user-ubuntu-abc123" in url, "URL should contain proxy path"
    assert url.endswith("/"), "URL should end with /"
    
    print("✓ URL generation passed")


def test_prefix_trailing_dash():
    """Test that trailing dash in prefix is handled"""
    print("\nTest 7: Prefix trailing dash handling")
    
    os.environ['CONTAINER_PREFIX'] = 'test-desktop-'
    proxy_path = "user-ubuntu-token"
    prefix = os.environ.get('CONTAINER_PREFIX', 'test-desktop').rstrip('-')
    
    url = f"https://{prefix}-{proxy_path}.hub.mdg-hamburg.de/"
    
    assert "test-desktop--user" not in url, "Should not have double dash"
    assert "test-desktop-user" in url, "Should have single dash"
    
    # Clean up
    del os.environ['CONTAINER_PREFIX']
    
    print("✓ Prefix trailing dash handling passed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Traefik Label Generation Tests")
    print("=" * 60)
    
    try:
        test_label_generation()
        test_hostname_rule()
        test_safe_name_sanitization()
        test_custom_domain()
        test_entrypoint()
        test_url_generation()
        test_prefix_trailing_dash()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
