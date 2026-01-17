#!/usr/bin/env python3
"""
Test script to verify audio WebSocket connectivity to Kasm container
"""
import websocket
import ssl
import base64
import sys

def test_audio_connection(host, port, username='kasm_user', password='password'):
    """
    Test WebSocket connection to container's audio port
    
    Args:
        host: Container host IP (e.g., '172.22.0.36')
        port: Audio port (e.g., 7001)
        username: Basic auth username
        password: Basic auth password
    """
    # Create Basic Auth header
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    # WebSocket URL
    url = f"wss://{host}:{port}/"
    
    print(f"Testing audio WebSocket connection to {url}")
    print(f"Using Basic Auth: {username}:****")
    print("-" * 60)
    
    try:
        # Create WebSocket connection with SSL verification disabled (self-signed cert)
        ws = websocket.create_connection(
            url,
            sslopt={"cert_reqs": ssl.CERT_NONE},
            header=[f"Authorization: Basic {credentials}"],
            timeout=5
        )
        
        print("✓ WebSocket connection successful!")
        print(f"  Connected to: {url}")
        
        # Try to receive initial data
        try:
            data = ws.recv()
            print(f"  Received initial data: {len(data)} bytes")
        except Exception as e:
            print(f"  No initial data received (this may be normal)")
        
        ws.close()
        print("✓ Connection closed cleanly")
        return True
        
    except websocket.WebSocketBadStatusException as e:
        print(f"✗ WebSocket connection failed with status {e.status_code}")
        print(f"  Response: {e.resp_headers}")
        return False
        
    except ssl.SSLError as e:
        print(f"✗ SSL Error: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Connection failed: {type(e).__name__}: {e}")
        return False

def test_via_apache(subdomain, username='kasm_user', password='password'):
    """
    Test WebSocket connection through Apache reverse proxy
    
    Args:
        subdomain: Full audio subdomain (e.g., 'test-audio-julian-kiedaisch-ubuntu-desktop.hub.mdg-hamburg.de')
    """
    # Create Basic Auth header
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    # WebSocket URL
    url = f"wss://{subdomain}/"
    
    print(f"Testing audio WebSocket through Apache: {url}")
    print(f"Using Basic Auth: {username}:****")
    print("-" * 60)
    
    try:
        # Create WebSocket connection
        ws = websocket.create_connection(
            url,
            header=[f"Authorization: Basic {credentials}"],
            timeout=5
        )
        
        print("✓ WebSocket connection through Apache successful!")
        print(f"  Connected to: {url}")
        
        # Try to receive initial data
        try:
            data = ws.recv()
            print(f"  Received initial data: {len(data)} bytes")
        except Exception as e:
            print(f"  No initial data received (this may be normal)")
        
        ws.close()
        print("✓ Connection closed cleanly")
        return True
        
    except websocket.WebSocketBadStatusException as e:
        print(f"✗ WebSocket connection failed with status {e.status_code}")
        print(f"  Response headers: {e.resp_headers}")
        if hasattr(e, 'resp_body'):
            print(f"  Response body: {e.resp_body[:500]}")
        return False
        
    except Exception as e:
        print(f"✗ Connection failed: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    print("Kasm Audio WebSocket Connection Test")
    print("=" * 60)
    
    # Test direct connection to container
    print("\n1. Testing DIRECT connection to container audio port...")
    direct_success = test_audio_connection('172.22.0.36', 7001)
    
    print("\n" + "=" * 60)
    
    # Test connection through Apache
    print("\n2. Testing connection THROUGH Apache reverse proxy...")
    apache_success = test_via_apache('test-audio-julian-kiedaisch-ubuntu-desktop.hub.mdg-hamburg.de')
    
    print("\n" + "=" * 60)
    print("\nTest Summary:")
    print(f"  Direct connection:  {'✓ PASS' if direct_success else '✗ FAIL'}")
    print(f"  Apache proxy:       {'✓ PASS' if apache_success else '✗ FAIL'}")
    
    if direct_success and not apache_success:
        print("\n⚠ Direct connection works but Apache proxy fails!")
        print("  Check Apache configuration and logs:")
        print("    - sudo tail -f /var/log/apache2/desktop_error.log")
        print("    - Verify RewriteMap is running: ps aux | grep get_container_target")
        print("    - Test RewriteMap: echo 'test-audio-...' | /opt/desktop.hub/get_container_target.py")
    
    sys.exit(0 if (direct_success and apache_success) else 1)
