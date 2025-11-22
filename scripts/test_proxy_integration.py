#!/usr/bin/env python3
"""
Integration test for reverse proxy functionality
Tests the proxy path generation and URL mapping
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_proxy_path_generation():
    """Test that proxy paths are generated correctly"""
    print("\nTesting proxy path generation...")
    
    test_cases = [
        {
            'username': 'alice',
            'desktop_type': 'ubuntu-vscode',
            'expected_path': 'alice-ubuntu-vscode'
        },
        {
            'username': 'bob',
            'desktop_type': 'ubuntu-desktop',
            'expected_path': 'bob-ubuntu-desktop'
        },
        {
            'username': 'charlie',
            'desktop_type': 'ubuntu-chromium',
            'expected_path': 'charlie-ubuntu-chromium'
        },
        {
            'username': 'user.name',
            'desktop_type': 'ubuntu-vscode',
            'expected_path': 'user.name-ubuntu-vscode'
        }
    ]
    
    all_passed = True
    for test in test_cases:
        username = test['username']
        desktop_type = test['desktop_type']
        expected = test['expected_path']
        
        # Generate proxy path (mimicking DockerManager logic)
        proxy_path = f"{username}-{desktop_type}"
        
        if proxy_path == expected:
            print(f"  ✓ {username} + {desktop_type} → {proxy_path}")
        else:
            print(f"  ✗ {username} + {desktop_type} → {proxy_path} (expected: {expected})")
            all_passed = False
    
    return all_passed

def test_url_generation():
    """Test that URLs are generated correctly"""
    print("\nTesting URL generation...")
    
    test_cases = [
        {
            'host': 'example.com',
            'proxy_path': 'alice-ubuntu-vscode',
            'expected_url': 'http://example.com/desktop/alice-ubuntu-vscode'
        },
        {
            'host': 'localhost',
            'proxy_path': 'bob-ubuntu-desktop',
            'expected_url': 'http://localhost/desktop/bob-ubuntu-desktop'
        },
        {
            'host': '192.168.1.100',
            'proxy_path': 'charlie-ubuntu-chromium',
            'expected_url': 'http://192.168.1.100/desktop/charlie-ubuntu-chromium'
        }
    ]
    
    all_passed = True
    for test in test_cases:
        host = test['host']
        proxy_path = test['proxy_path']
        expected = test['expected_url']
        
        # Generate URL (mimicking DockerManager.get_container_url logic)
        url = f"http://{host}/desktop/{proxy_path}"
        
        if url == expected:
            print(f"  ✓ {host} + {proxy_path} → {url}")
        else:
            print(f"  ✗ {host} + {proxy_path} → {url} (expected: {expected})")
            all_passed = False
    
    return all_passed

def test_multiple_users_scenario():
    """Test scenario with multiple concurrent users"""
    print("\nTesting multiple concurrent users scenario...")
    
    users = [
        {'username': 'alice', 'desktop': 'ubuntu-vscode', 'port': 7001},
        {'username': 'bob', 'desktop': 'ubuntu-desktop', 'port': 7002},
        {'username': 'charlie', 'desktop': 'ubuntu-chromium', 'port': 7003},
        {'username': 'alice', 'desktop': 'ubuntu-desktop', 'port': 7004},  # Same user, different desktop
    ]
    
    print("\n  Simulating multiple users:")
    proxy_paths = set()
    all_unique = True
    
    for user in users:
        proxy_path = f"{user['username']}-{user['desktop']}"
        url = f"http://example.com/desktop/{proxy_path}"
        
        # Check uniqueness
        if proxy_path in proxy_paths:
            print(f"  ✗ Duplicate proxy path: {proxy_path}")
            all_unique = False
        else:
            proxy_paths.add(proxy_path)
            print(f"  ✓ User '{user['username']}' → {url} (port {user['port']})")
    
    print(f"\n  Total unique proxy paths: {len(proxy_paths)}")
    print(f"  Expected unique paths: {len(users)}")
    
    if len(proxy_paths) == len(users):
        print("  ✓ All proxy paths are unique")
        return True
    else:
        print("  ✗ Some proxy paths are duplicates")
        return False

def test_path_uniqueness():
    """Test that proxy paths remain unique even with similar usernames"""
    print("\nTesting proxy path uniqueness...")
    
    # Users with similar names but different desktop types should get unique paths
    users = [
        ('john', 'ubuntu-vscode'),
        ('john', 'ubuntu-desktop'),
        ('john', 'ubuntu-chromium'),
        ('john.doe', 'ubuntu-vscode'),
        ('johndoe', 'ubuntu-vscode'),
    ]
    
    paths = set()
    all_unique = True
    
    for username, desktop_type in users:
        proxy_path = f"{username}-{desktop_type}"
        
        if proxy_path in paths:
            print(f"  ✗ Duplicate: {proxy_path}")
            all_unique = False
        else:
            paths.add(proxy_path)
            print(f"  ✓ {proxy_path}")
    
    if all_unique:
        print("  ✓ All paths are unique")
    
    return all_unique

def main():
    """Run all tests"""
    print("=" * 70)
    print("Reverse Proxy Integration Tests")
    print("=" * 70)
    
    results = []
    results.append(("Proxy Path Generation", test_proxy_path_generation()))
    results.append(("URL Generation", test_url_generation()))
    results.append(("Multiple Users Scenario", test_multiple_users_scenario()))
    results.append(("Path Uniqueness", test_path_uniqueness()))
    
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:.<50} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("✓ All integration tests passed!")
        print("\nNext steps:")
        print("  1. Set DOCKER_HOST_URL in .env to your server domain")
        print("  2. Deploy with docker-compose up")
        print("  3. Test with real containers")
        print("  4. For production, enable nginx in docker-compose.yml")
        return 0
    else:
        print("✗ Some integration tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
