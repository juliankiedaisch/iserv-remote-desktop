#!/usr/bin/env python3
"""
Remote Proxy WebSocket Test

Tests WebSocket connection through the Apache proxy (desktop.hub.mdg-hamburg.de)
with a test authentication token that bypasses OAuth2.
"""

import socket
import ssl
import base64
import os
import sys

PROXY_HOST = "desktop.hub.mdg-hamburg.de"
PROXY_PORT = 443
TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"  # Change this to your actual container

print("=" * 70)
print(f"REMOTE PROXY WEBSOCKET TEST")
print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
print(f"Container: {TEST_CONTAINER}")
print("=" * 70)

# Step 1: Test HTTPS connection
print(f"\n[1] Testing HTTPS connection to {PROXY_HOST}...")
try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=PROXY_HOST) as ssock:
            print(f"    ✓ SSL connection established")
            print(f"    TLS version: {ssock.version()}")
except Exception as e:
    print(f"    ✗ Connection failed: {e}")
    sys.exit(1)

# Step 2: Test HTTP request
print(f"\n[2] Testing HTTP request to /desktop/{TEST_CONTAINER}...")
try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=PROXY_HOST) as ssock:
            request = (
                f"GET /desktop/{TEST_CONTAINER} HTTP/1.1\r\n"
                f"Host: {PROXY_HOST}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            
            ssock.sendall(request.encode())
            
            response = b''
            while True:
                chunk = ssock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if len(response) > 1024:  # Just read headers
                    break
            
            response_str = response.decode('utf-8', errors='ignore')
            status_line = response_str.split('\r\n')[0]
            
            print(f"    Response: {status_line}")
            
            if '200' in status_line or '302' in status_line:
                print(f"    ✓ HTTP request successful")
            else:
                print(f"    ⚠ Unexpected status")
                
except Exception as e:
    print(f"    ✗ Request failed: {e}")

# Step 3: Test WebSocket handshake through proxy
print(f"\n[3] Testing WebSocket handshake to wss://{PROXY_HOST}/websockify...")
try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=PROXY_HOST) as ssock:
            ws_key = base64.b64encode(os.urandom(16)).decode()
            
            request = (
                f"GET /websockify HTTP/1.1\r\n"
                f"Host: {PROXY_HOST}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"Origin: https://{PROXY_HOST}\r\n"
                f"Referer: https://{PROXY_HOST}/desktop/{TEST_CONTAINER}\r\n"
                f"\r\n"
            )
            
            print("    Sending WebSocket upgrade request...")
            print(f"    (with Referer: /desktop/{TEST_CONTAINER})")
            
            ssock.sendall(request.encode())
            
            # Read response with timeout
            ssock.settimeout(5)
            response = b''
            
            try:
                while True:
                    chunk = ssock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    if b'\r\n\r\n' in response:
                        break
            except socket.timeout:
                pass
            
            response_str = response.decode('utf-8', errors='ignore')
            lines = response_str.split('\r\n')
            
            print("\n    Response:")
            for line in lines[:15]:
                if line:
                    print(f"      {line}")
            
            status_line = lines[0] if lines else ''
            
            if '101' in status_line:
                print("\n    ✓✓✓ SUCCESS! HTTP 101 Switching Protocols")
                print("        WebSocket upgrade successful!")
                print("        Everything is working correctly!")
            elif '502' in status_line:
                print("\n    ✗✗✗ PROBLEM: HTTP 502 Bad Gateway")
                print("        Apache cannot reach Flask, or Flask returned error")
                print("        Check:")
                print("        1. Flask is running on 172.22.0.27:5020")
                print("        2. Apache can reach Flask (firewall?)")
                print("        3. Flask logs for errors")
            elif '404' in status_line:
                print("\n    ✗✗✗ PROBLEM: HTTP 404 Not Found")
                print("        Container not found or session missing")
                print("        Make sure:")
                print(f"        1. Container '{TEST_CONTAINER}' exists and is running")
                print("        2. You have accessed the desktop page first to create session")
            elif '403' in status_line or '401' in status_line:
                print("\n    ✗✗✗ PROBLEM: Authentication required")
                print("        You need to authenticate first")
                print("        Open the desktop page in a browser to create a session")
            elif '426' in status_line:
                print("\n    ✗✗✗ PROBLEM: HTTP 426 Upgrade Required")
                print("        Apache is not passing WebSocket upgrade header")
                print("        Check Apache configuration for 'upgrade=any' parameter")
            elif not response:
                print("\n    ✗✗✗ PROBLEM: No response received")
                print("        Connection closed immediately")
                print("        This means:")
                print("        1. Apache connected to Flask")
                print("        2. But Flask closed the connection immediately")
                print("        3. Check Flask logs for the reason")
            else:
                print(f"\n    ⚠⚠⚠ UNEXPECTED: {status_line}")
                
except Exception as e:
    print(f"    ✗ Request failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSIS:")
print("=" * 70)
print("""
Based on the test results:

If you got 502 Bad Gateway:
  → Apache cannot communicate with Flask
  → Check network connectivity between servers
  → Verify Flask is running on 172.22.0.27:5020

If you got 404 Not Found:
  → Container not found in database
  → Access the desktop page first to start a container
  → Make sure the container name matches

If you got no response / immediate close:
  → Apache connected but Flask closed immediately
  → This is the "Error 1005" you've been seeing
  → Flask is NOT receiving the WebSocket properly from Apache
  → Apache's 'upgrade=any' parameter may not be working

If you got 101 Switching Protocols:
  → Everything is working! ✓
  → If browser still fails, it's a browser/cookie issue

MOST LIKELY ISSUE:
  Apache's 'upgrade=any' parameter requires Apache 2.4.47+
  Check Apache version: apache2 -v
  
  If Apache is older:
  → Upgrade Apache, OR
  → Use alternative configuration with RewriteRule (ask for details)
""")

print("\nTo check Apache version on proxy server:")
print("  ssh to desktop.hub.mdg-hamburg.de")
print("  Run: apache2 -v")
