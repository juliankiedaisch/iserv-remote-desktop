#!/usr/bin/env python3
"""
Test script to diagnose why the Flask /websockify route is not being called
"""
import socket
import ssl
import base64
import requests
import time

def test_flask_http():
    """Test if Flask is responding to regular HTTP requests"""
    print("\n" + "="*80)
    print("TEST 1: Flask HTTP Response")
    print("="*80)
    try:
        response = requests.get('http://localhost:5020/', timeout=5)
        print(f"✓ Flask is responding on port 5020")
        print(f"  Status: {response.status_code}")
        print(f"  Content length: {len(response.text)} bytes")
        return True
    except Exception as e:
        print(f"✗ Flask is NOT responding: {e}")
        return False

def test_websocket_endpoint_http():
    """Test if /websockify endpoint responds to regular HTTP GET"""
    print("\n" + "="*80)
    print("TEST 2: /websockify HTTP GET (non-WebSocket)")
    print("="*80)
    try:
        response = requests.get('http://localhost:5020/websockify', timeout=5)
        print(f"✓ /websockify responded to HTTP GET")
        print(f"  Status: {response.status_code}")
        print(f"  Content: {response.text[:200]}")
        return True
    except Exception as e:
        print(f"✗ /websockify did not respond: {e}")
        return False

def test_websocket_upgrade_raw():
    """Test WebSocket upgrade request using raw socket"""
    print("\n" + "="*80)
    print("TEST 3: WebSocket Upgrade to /websockify (raw socket)")
    print("="*80)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('localhost', 5020))
        
        # Send WebSocket upgrade request
        key = base64.b64encode(b"test_key_12345678").decode()
        request = (
            f"GET /websockify HTTP/1.1\r\n"
            f"Host: localhost:5020\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        
        print(f"Sending WebSocket upgrade request:")
        print(request)
        
        sock.sendall(request.encode())
        response = sock.recv(4096).decode('utf-8', errors='ignore')
        
        print(f"\n✓ Received response:")
        print(response[:500])
        
        # Check if we got 101 Switching Protocols
        if "101" in response.split('\r\n')[0]:
            print("\n✓ WebSocket handshake successful (101 Switching Protocols)")
        else:
            print(f"\n✗ Expected 101, got: {response.split(chr(10))[0]}")
        
        sock.close()
        return True
    except Exception as e:
        print(f"✗ WebSocket upgrade failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_websocket_with_subdomain():
    """Test WebSocket upgrade with subdomain in Host header"""
    print("\n" + "="*80)
    print("TEST 4: WebSocket Upgrade with subdomain Host header")
    print("="*80)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('localhost', 5020))
        
        # Send WebSocket upgrade with subdomain Host header
        key = base64.b64encode(b"test_key_12345678").decode()
        request = (
            f"GET /websockify HTTP/1.1\r\n"
            f"Host: julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        
        print(f"Sending WebSocket upgrade with subdomain:")
        print(request)
        
        sock.sendall(request.encode())
        response = sock.recv(4096).decode('utf-8', errors='ignore')
        
        print(f"\n✓ Received response:")
        print(response[:500])
        
        # Check response
        status_line = response.split('\r\n')[0]
        if "101" in status_line:
            print("\n✓ WebSocket handshake successful with subdomain")
        elif "404" in status_line:
            print("\n⚠ Got 404 - Flask route not found")
        elif "403" in status_line:
            print("\n⚠ Got 403 - Forbidden (container not found?)")
        else:
            print(f"\n⚠ Unexpected response: {status_line}")
        
        sock.close()
        return True
    except Exception as e:
        print(f"✗ WebSocket upgrade with subdomain failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_check_route_registration():
    """Test if Flask routes are properly registered"""
    print("\n" + "="*80)
    print("TEST 5: Check Flask Route Registration")
    print("="*80)
    try:
        response = requests.get('http://localhost:5020/', timeout=5)
        # Try to trigger an error to see registered routes
        response = requests.get('http://localhost:5020/nonexistent_route_test', timeout=5)
        if response.status_code == 404:
            print("✓ Flask is routing requests (404 for nonexistent route)")
            print(f"  Response: {response.text[:200]}")
        return True
    except Exception as e:
        print(f"⚠ Could not test route registration: {e}")
        return False

def main():
    print("\n" + "#"*80)
    print("# WebSocket Route Debugging Test Suite")
    print("# Target: Flask on localhost:5020")
    print("#"*80)
    
    time.sleep(1)  # Give Flask a moment to fully start
    
    results = []
    results.append(("Flask HTTP", test_flask_http()))
    results.append(("WebSocket endpoint HTTP", test_websocket_endpoint_http()))
    results.append(("WebSocket upgrade raw", test_websocket_upgrade_raw()))
    results.append(("WebSocket with subdomain", test_websocket_with_subdomain()))
    results.append(("Route registration", test_check_route_registration()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    print("IMPORTANT: Check Flask terminal output for [ROUTE ENTRY] messages")
    print("If no [ROUTE ENTRY] appears, the route handler is not being called")
    print("="*80)

if __name__ == '__main__':
    main()
