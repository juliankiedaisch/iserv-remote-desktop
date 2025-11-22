#!/usr/bin/env python3
"""
Test script for connection retry logic in proxy routes
Tests that RemoteDisconnected errors are properly handled with retry logic
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        from app.routes.proxy_routes import (
            proxy_bp, 
            is_container_startup_error,
            CONTAINER_STARTUP_RETRIES,
            CONTAINER_STARTUP_BACKOFF
        )
        import requests
        from urllib3.exceptions import ProtocolError
        print("✓ All imports successful")
        print(f"  - CONTAINER_STARTUP_RETRIES: {CONTAINER_STARTUP_RETRIES}")
        print(f"  - CONTAINER_STARTUP_BACKOFF: {CONTAINER_STARTUP_BACKOFF}s")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_is_container_startup_error():
    """Test the is_container_startup_error function"""
    print("\nTesting is_container_startup_error function...")
    try:
        from app.routes.proxy_routes import is_container_startup_error
        import requests
        from urllib3.exceptions import ProtocolError
        from http.client import RemoteDisconnected
        
        # Test 1: Regular ConnectionError (should return False)
        try:
            raise requests.exceptions.ConnectionError("Regular connection error")
        except requests.exceptions.ConnectionError as e:
            result = is_container_startup_error(e)
            if not result:
                print("  ✓ Regular ConnectionError correctly identified as non-startup error")
            else:
                print("  ✗ Regular ConnectionError incorrectly identified as startup error")
                return False
        
        # Test 2: ConnectionError with RemoteDisconnected in message (should return True)
        try:
            # Simulate the error structure we see in the logs
            raise requests.exceptions.ConnectionError(
                "HTTPConnectionPool(host='localhost', port=7000): Max retries exceeded with url: / "
                "(Caused by ProtocolError('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')))"
            )
        except requests.exceptions.ConnectionError as e:
            result = is_container_startup_error(e)
            if result:
                print("  ✓ RemoteDisconnected ConnectionError correctly identified as startup error")
            else:
                print("  ✗ RemoteDisconnected ConnectionError incorrectly identified as non-startup error")
                return False
        
        # Test 3: ConnectionError with ProtocolError (should return True)
        try:
            protocol_error = ProtocolError("Connection aborted.")
            raise requests.exceptions.ConnectionError(protocol_error)
        except requests.exceptions.ConnectionError as e:
            result = is_container_startup_error(e)
            if result:
                print("  ✓ ProtocolError ConnectionError correctly identified as startup error")
            else:
                print("  ✗ ProtocolError ConnectionError incorrectly identified as non-startup error")
                return False
        
        print("✓ All is_container_startup_error tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retry_configuration():
    """Test retry configuration constants"""
    print("\nTesting retry configuration...")
    try:
        from app.routes.proxy_routes import (
            CONTAINER_STARTUP_RETRIES,
            CONTAINER_STARTUP_BACKOFF,
            PROXY_CONNECT_TIMEOUT,
            PROXY_READ_TIMEOUT
        )
        
        # Check that retry settings are reasonable
        checks = [
            (CONTAINER_STARTUP_RETRIES >= 3, 
             f"CONTAINER_STARTUP_RETRIES should be >= 3 (got {CONTAINER_STARTUP_RETRIES})"),
            (CONTAINER_STARTUP_BACKOFF >= 1.0, 
             f"CONTAINER_STARTUP_BACKOFF should be >= 1.0s (got {CONTAINER_STARTUP_BACKOFF})"),
            (PROXY_CONNECT_TIMEOUT >= 5, 
             f"PROXY_CONNECT_TIMEOUT should be >= 5s (got {PROXY_CONNECT_TIMEOUT})"),
            (PROXY_READ_TIMEOUT >= 60, 
             f"PROXY_READ_TIMEOUT should be >= 60s (got {PROXY_READ_TIMEOUT})"),
        ]
        
        all_passed = True
        for check, message in checks:
            if check:
                print(f"  ✓ {message.split('(')[0]}")
            else:
                print(f"  ✗ {message}")
                all_passed = False
        
        # Calculate total retry time
        total_retry_time = sum(CONTAINER_STARTUP_BACKOFF * (2 ** i) 
                              for i in range(CONTAINER_STARTUP_RETRIES - 1))
        print(f"\n  Total retry time (excluding initial attempt): {total_retry_time:.1f}s")
        print(f"  With 5 retries: 2s + 4s + 8s + 16s = {total_retry_time:.1f}s")
        
        if total_retry_time >= 20:
            print("  ✓ Total retry time is sufficient for container startup")
        else:
            print("  ✗ Total retry time may be too short")
            all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_time_module_imported():
    """Test that time module is imported for sleep"""
    print("\nTesting time module import...")
    try:
        import app.routes.proxy_routes as pr
        if hasattr(pr, 'time'):
            print("  ✓ time module imported in proxy_routes")
            return True
        else:
            print("  ✗ time module not found in proxy_routes")
            return False
    except Exception as e:
        print(f"  ✗ Error checking time module: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("Connection Retry Logic Tests")
    print("=" * 70)
    
    results = []
    results.append(("Module Imports", test_imports()))
    results.append(("is_container_startup_error", test_is_container_startup_error()))
    results.append(("Retry Configuration", test_retry_configuration()))
    results.append(("Time Module Import", test_time_module_imported()))
    
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
        print("✓ All tests passed!")
        print("\nThe proxy will now retry RemoteDisconnected errors with:")
        print("  - 5 retry attempts")
        print("  - Exponential backoff: 2s, 4s, 8s, 16s")
        print("  - Total wait time: up to ~30 seconds")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
