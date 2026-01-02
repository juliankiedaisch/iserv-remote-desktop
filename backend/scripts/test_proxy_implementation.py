#!/usr/bin/env python3
"""
Test script for reverse proxy implementation
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        from app.models.containers import Container
        from app.services.docker_manager import DockerManager
        from app.routes.proxy_routes import proxy_bp
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_container_model():
    """Test that Container model has proxy_path field"""
    print("\nTesting Container model...")
    try:
        from app.models.containers import Container
        
        # Check if proxy_path field exists in the model
        if hasattr(Container, 'proxy_path'):
            print("✓ Container model has proxy_path field")
        else:
            print("✗ Container model missing proxy_path field")
            return False
        
        # Check if get_by_proxy_path method exists
        if hasattr(Container, 'get_by_proxy_path'):
            print("✓ Container model has get_by_proxy_path method")
        else:
            print("✗ Container model missing get_by_proxy_path method")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Container model test failed: {e}")
        return False

def test_docker_manager():
    """Test DockerManager proxy path generation"""
    print("\nTesting DockerManager...")
    try:
        # We can't fully test without Docker, but we can check the methods exist
        from app.services.docker_manager import DockerManager
        
        if hasattr(DockerManager, 'get_container_url'):
            print("✓ DockerManager has get_container_url method")
        else:
            print("✗ DockerManager missing get_container_url method")
            return False
        
        return True
    except Exception as e:
        print(f"✗ DockerManager test failed: {e}")
        return False

def test_proxy_routes():
    """Test that proxy routes blueprint exists"""
    print("\nTesting proxy routes...")
    try:
        from app.routes.proxy_routes import proxy_bp
        
        if proxy_bp:
            print("✓ Proxy blueprint created successfully")
            print(f"  Blueprint name: {proxy_bp.name}")
        else:
            print("✗ Proxy blueprint is None")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Proxy routes test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Reverse Proxy Implementation Tests")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Container Model", test_container_model()))
    results.append(("DockerManager", test_docker_manager()))
    results.append(("Proxy Routes", test_proxy_routes()))
    
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
