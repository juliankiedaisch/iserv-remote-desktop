#!/usr/bin/env python3
"""
Test script to verify retry logic in proxy routes
"""
import sys
import os
import traceback

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_retry_session_creation():
    """Test that retry session can be created with correct configuration"""
    print("Testing retry session creation...")
    try:
        from app.routes.proxy_routes import create_retry_session
        
        # Create a session with default parameters
        session = create_retry_session()
        
        # Verify session is created
        if session is None:
            print("✗ Session creation returned None")
            return False
        
        # Check that adapters are mounted
        if 'http://' not in session.adapters or 'https://' not in session.adapters:
            print("✗ HTTP/HTTPS adapters not properly mounted")
            return False
        
        # Get the adapter to check retry configuration
        adapter = session.adapters['http://']
        if adapter.max_retries is None:
            print("✗ No retry configuration found")
            return False
        
        print(f"✓ Session created successfully with retry configuration")
        print(f"  Retry total: {adapter.max_retries.total}")
        print(f"  Backoff factor: {adapter.max_retries.backoff_factor}")
        print(f"  Status forcelist: {adapter.max_retries.status_forcelist}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to create retry session: {e}")
        traceback.print_exc()
        return False

def test_retry_session_custom_params():
    """Test that retry session accepts custom parameters"""
    print("\nTesting retry session with custom parameters...")
    try:
        from app.routes.proxy_routes import create_retry_session
        
        # Create a session with custom parameters (using frozenset)
        session = create_retry_session(retries=5, backoff_factor=1.0, status_forcelist=frozenset([500, 503]))
        
        # Verify configuration
        adapter = session.adapters['http://']
        
        if adapter.max_retries.total != 5:
            print(f"✗ Expected 5 retries, got {adapter.max_retries.total}")
            return False
        
        if adapter.max_retries.backoff_factor != 1.0:
            print(f"✗ Expected backoff factor 1.0, got {adapter.max_retries.backoff_factor}")
            return False
        
        # Use frozenset for comparison as that's what Retry uses internally
        expected_status_forcelist = frozenset([500, 503])
        if adapter.max_retries.status_forcelist != expected_status_forcelist:
            print(f"✗ Unexpected status forcelist: {adapter.max_retries.status_forcelist}")
            return False
        
        print("✓ Custom parameters applied correctly")
        print(f"  Retries: {adapter.max_retries.total}")
        print(f"  Backoff factor: {adapter.max_retries.backoff_factor}")
        print(f"  Status forcelist: {adapter.max_retries.status_forcelist}")
        
        return True
    except Exception as e:
        print(f"✗ Failed with custom parameters: {e}")
        traceback.print_exc()
        return False

def test_proxy_route_imports():
    """Test that all required imports work"""
    print("\nTesting proxy route imports...")
    try:
        from app.routes.proxy_routes import proxy_bp, create_retry_session
        
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Proxy Retry Logic Tests")
    print("=" * 60)
    
    results = []
    results.append(("Proxy Route Imports", test_proxy_route_imports()))
    results.append(("Retry Session Creation", test_retry_session_creation()))
    results.append(("Custom Parameters", test_retry_session_custom_params()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:.<40} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
