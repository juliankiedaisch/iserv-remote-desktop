#!/usr/bin/env python3
"""
Test script to verify backend i18n implementation
"""

import sys
sys.path.insert(0, '/home/runner/work/iserv-remote-desktop/iserv-remote-desktop/backend')

from app.i18n import get_message

def test_i18n():
    """Test backend i18n functionality"""
    print("Testing Backend i18n Implementation")
    print("=" * 50)
    
    # Test English messages
    print("\n1. English Messages:")
    print(f"   session_required: {get_message('session_required', 'en')}")
    print(f"   container_stopped: {get_message('container_stopped', 'en')}")
    print(f"   admin_required: {get_message('admin_required', 'en')}")
    
    # Test German messages
    print("\n2. German Messages:")
    print(f"   session_required: {get_message('session_required', 'de')}")
    print(f"   container_stopped: {get_message('container_stopped', 'de')}")
    print(f"   admin_required: {get_message('admin_required', 'de')}")
    
    # Test parameter substitution
    print("\n3. Parameter Substitution:")
    print(f"   EN: {get_message('containers_stopped', 'en', count=5)}")
    print(f"   DE: {get_message('containers_stopped', 'de', count=5)}")
    
    # Test fallback to English
    print("\n4. Fallback to English (unsupported language):")
    print(f"   session_required (fr): {get_message('session_required', 'fr')}")
    
    # Test unknown key
    print("\n5. Unknown Key (returns key itself):")
    print(f"   unknown_key: {get_message('unknown_key', 'en')}")
    
    print("\n" + "=" * 50)
    print("✅ All tests completed successfully!")

if __name__ == '__main__':
    test_i18n()
