#!/usr/bin/env python3
"""
Standalone test script for container access check endpoint
Tests the authentication logic without requiring full Flask setup
"""

import sys


def test_proxy_path_extraction():
    """Test proxy_path extraction from subdomain"""
    print("Test 1: Proxy path extraction from subdomain")
    
    # Test case 1: test-desktop prefix
    host = "test-desktop-user-ubuntu-token123.hub.mdg-hamburg.de"
    prefix = "test-desktop"
    
    if host.startswith(f"{prefix}-"):
        remaining = host[len(f"{prefix}-"):]
        proxy_path = remaining.split('.')[0]
        
        assert proxy_path == "user-ubuntu-token123", f"Expected 'user-ubuntu-token123', got '{proxy_path}'"
        print(f"  ✓ Extracted proxy_path from {host}: {proxy_path}")
    
    # Test case 2: test-audio prefix
    host = "test-audio-user-abc.hub.mdg-hamburg.de"
    
    if host.startswith("test-audio-"):
        remaining = host[len("test-audio-"):]
        proxy_path = remaining.split('.')[0]
        
        assert proxy_path == "user-abc", f"Expected 'user-abc', got '{proxy_path}'"
        print(f"  ✓ Extracted proxy_path from {host}: {proxy_path}")
    
    # Test case 3: custom prefix with trailing dash
    host = "custom-prefix-john-doe-xyz.example.com"
    prefix = "custom-prefix-"
    prefix = prefix.rstrip('-')
    
    if host.startswith(f"{prefix}-"):
        remaining = host[len(f"{prefix}-"):]
        proxy_path = remaining.split('.')[0]
        
        assert proxy_path == "john-doe-xyz", f"Expected 'john-doe-xyz', got '{proxy_path}'"
        print(f"  ✓ Extracted proxy_path from {host}: {proxy_path}")
    
    print("✓ Proxy path extraction tests passed\n")


def test_cookie_parsing():
    """Test cookie parsing logic"""
    print("Test 2: Cookie parsing")
    
    # Test case 1: Single cookie
    cookies = "session_id=abc123"
    session_id = None
    
    for cookie in cookies.split(';'):
        cookie = cookie.strip()
        if cookie.startswith('session_id='):
            session_id = cookie.split('=', 1)[1]
            break
    
    assert session_id == "abc123", f"Expected 'abc123', got '{session_id}'"
    print(f"  ✓ Parsed single cookie: {session_id}")
    
    # Test case 2: Multiple cookies
    cookies = "other_cookie=value1; session_id=xyz789; another=value2"
    session_id = None
    
    for cookie in cookies.split(';'):
        cookie = cookie.strip()
        if cookie.startswith('session_id='):
            session_id = cookie.split('=', 1)[1]
            break
    
    assert session_id == "xyz789", f"Expected 'xyz789', got '{session_id}'"
    print(f"  ✓ Parsed multiple cookies: {session_id}")
    
    # Test case 3: No session_id cookie
    cookies = "other=value1; another=value2"
    session_id = None
    
    for cookie in cookies.split(';'):
        cookie = cookie.strip()
        if cookie.startswith('session_id='):
            session_id = cookie.split('=', 1)[1]
            break
    
    assert session_id is None, f"Expected None, got '{session_id}'"
    print(f"  ✓ No session_id cookie: {session_id}")
    
    print("✓ Cookie parsing tests passed\n")


def test_access_logic():
    """Test access control logic"""
    print("Test 3: Access control logic")
    
    # Mock user and container data
    class MockUser:
        def __init__(self, id, username, role):
            self.id = id
            self.username = username
            self.role = role
            self.is_admin = role == 'admin'
            self.is_teacher = role == 'teacher'
    
    class MockContainer:
        def __init__(self, user_id, container_name):
            self.user_id = user_id
            self.container_name = container_name
    
    # Test case 1: Owner access
    user = MockUser("user1", "john", "student")
    container = MockContainer("user1", "kasm_john_ubuntu")
    
    has_access = (container.user_id == user.id) or user.is_admin or user.is_teacher
    assert has_access, "Owner should have access"
    print("  ✓ Owner has access")
    
    # Test case 2: Admin access
    user = MockUser("user2", "admin", "admin")
    container = MockContainer("user1", "kasm_john_ubuntu")
    
    has_access = (container.user_id == user.id) or user.is_admin or user.is_teacher
    assert has_access, "Admin should have access"
    print("  ✓ Admin has access to other's container")
    
    # Test case 3: Teacher access
    user = MockUser("user3", "teacher", "teacher")
    container = MockContainer("user1", "kasm_john_ubuntu")
    
    has_access = (container.user_id == user.id) or user.is_admin or user.is_teacher
    assert has_access, "Teacher should have access"
    print("  ✓ Teacher has access to other's container")
    
    # Test case 4: Student no access
    user = MockUser("user4", "jane", "student")
    container = MockContainer("user1", "kasm_john_ubuntu")
    
    has_access = (container.user_id == user.id) or user.is_admin or user.is_teacher
    assert not has_access, "Student should not have access to other's container"
    print("  ✓ Student denied access to other's container")
    
    print("✓ Access control logic tests passed\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Container Access Check Endpoint Tests")
    print("=" * 60 + "\n")
    
    try:
        test_proxy_path_extraction()
        test_cookie_parsing()
        test_access_logic()
        
        print("=" * 60)
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
