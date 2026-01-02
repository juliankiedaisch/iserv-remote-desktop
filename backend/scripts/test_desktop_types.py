#!/usr/bin/env python3
"""
Test script for desktop types and assignments API
"""

import requests
import json
import sys

# Configuration
API_BASE = "http://localhost:5020/api"
# Note: Replace with actual admin session ID
SESSION_ID = "your-admin-session-id"

def print_response(response):
    """Pretty print response"""
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print()

def test_list_desktop_types():
    """Test listing desktop types"""
    print("=" * 50)
    print("TEST: List Desktop Types")
    print("=" * 50)
    
    response = requests.get(
        f"{API_BASE}/admin/desktops/types",
        headers={"X-Session-ID": SESSION_ID}
    )
    print_response(response)
    return response.json() if response.status_code == 200 else None

def test_create_desktop_type():
    """Test creating a desktop type"""
    print("=" * 50)
    print("TEST: Create Desktop Type")
    print("=" * 50)
    
    data = {
        "name": "Python Development",
        "docker_image": "kasmweb/python:1.16.0",
        "description": "Python development environment with Jupyter",
        "icon": "🐍",
        "enabled": True
    }
    
    response = requests.post(
        f"{API_BASE}/admin/desktops/types",
        headers={
            "X-Session-ID": SESSION_ID,
            "Content-Type": "application/json"
        },
        json=data
    )
    print_response(response)
    return response.json() if response.status_code == 200 else None

def test_create_assignment(desktop_type_id, group_name):
    """Test creating an assignment"""
    print("=" * 50)
    print(f"TEST: Create Assignment (Group: {group_name})")
    print("=" * 50)
    
    data = {"group_name": group_name}
    
    response = requests.post(
        f"{API_BASE}/admin/desktops/types/{desktop_type_id}/assignments",
        headers={
            "X-Session-ID": SESSION_ID,
            "Content-Type": "application/json"
        },
        json=data
    )
    print_response(response)
    return response.json() if response.status_code == 200 else None

def test_list_assignments(desktop_type_id):
    """Test listing assignments"""
    print("=" * 50)
    print(f"TEST: List Assignments for Desktop Type {desktop_type_id}")
    print("=" * 50)
    
    response = requests.get(
        f"{API_BASE}/admin/desktops/types/{desktop_type_id}/assignments",
        headers={"X-Session-ID": SESSION_ID}
    )
    print_response(response)
    return response.json() if response.status_code == 200 else None

def main():
    if SESSION_ID == "your-admin-session-id":
        print("ERROR: Please set SESSION_ID in the script to your admin session ID")
        print("\nTo get your session ID:")
        print("1. Login as admin at http://localhost:5020")
        print("2. Open browser console")
        print("3. Run: localStorage.getItem('session_id')")
        sys.exit(1)
    
    print("Testing Desktop Types API")
    print("=" * 50)
    print()
    
    # Test 1: List existing desktop types
    result = test_list_desktop_types()
    
    # Test 2: Create a new desktop type
    result = test_create_desktop_type()
    if result and result.get('success'):
        desktop_type_id = result.get('desktop_type', {}).get('id')
        
        # Test 3: Create assignment
        if desktop_type_id:
            test_create_assignment(desktop_type_id, "lehrende")
            
            # Test 4: List assignments
            test_list_assignments(desktop_type_id)
    
    print()
    print("=" * 50)
    print("Tests completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()
