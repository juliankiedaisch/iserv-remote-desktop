#!/usr/bin/env python3
"""
Simple WebSocket Handshake Test

Tests the WebSocket handshake to Flask without needing database access.
"""

import socket
import base64
import os

print("=" * 70)
print("WEBSOCKET HANDSHAKE TEST")
print("=" * 70)

# Step 1: Check Flask is running
print("\n[1] Checking if Flask is running on port 5020...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(('localhost', 5020))
    sock.close()
    
    if result == 0:
        print("    ✓ Flask is listening on localhost:5020")
    else:
        print("    ✗ Flask is NOT listening on localhost:5020")
        print("      Start Flask first: python run.py")
        exit(1)
except Exception as e:
    print(f"    ✗ Error: {e}")
    exit(1)

# Step 2: Send WebSocket upgrade request
print("\n[2] Sending WebSocket upgrade request to /websockify...")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('localhost', 5020))
    
    # Generate WebSocket key
    ws_key = base64.b64encode(os.urandom(16)).decode()
    
    # Build HTTP upgrade request
    request = (
        f"GET /websockify HTTP/1.1\r\n"
        f"Host: localhost:5020\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"Referer: https://desktop.hub.mdg-hamburg.de/desktop/test-container\r\n"
        f"\r\n"
    )
    
    print("    Sending request:")
    for line in request.strip().split('\r\n'):
        if line:
            print(f"      {line}")
    
    sock.sendall(request.encode())
    
    # Receive response
    response = b''
    sock.settimeout(3)
    
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            # Break after headers (empty line)
            if b'\r\n\r\n' in response:
                break
    except socket.timeout:
        pass
    
    sock.close()
    
    # Parse response
    response_str = response.decode('utf-8', errors='ignore')
    lines = response_str.split('\r\n')
    
    print("\n    Response:")
    for line in lines[:10]:  # First 10 lines
        print(f"      {line}")
    
    # Check status code
    if '101' in lines[0]:
        print("\n    ✓✓✓ SUCCESS! HTTP 101 Switching Protocols")
        print("        Flask's gevent-websocket is working correctly!")
        print("        The problem is likely in Apache configuration.")
    elif '502' in lines[0]:
        print("\n    ✗✗✗ PROBLEM: HTTP 502 Bad Gateway")
        print("        Flask cannot handle WebSocket (no wsgi.websocket object)")
        print("        This happens when Apache uses ws:// protocol")
        print("        SOLUTION: Use 'upgrade=any' parameter in Apache ProxyPass")
    elif '307' in lines[0]:
        print("\n    ✗✗✗ PROBLEM: HTTP 307 Redirect")
        print("        Flask is redirecting instead of handling WebSocket")
        print("        This happens when Flask doesn't have wsgi.websocket")
    elif '404' in lines[0]:
        print("\n    ✗✗✗ PROBLEM: HTTP 404 Not Found")
        print("        Container or session not found")
        print("        Start a container from the web UI first")
    elif '200' in lines[0]:
        print("\n    ⚠ INFO: HTTP 200 OK (not WebSocket)")
        print("        Flask received the request but not as WebSocket")
        print("        Check Flask logs for details")
    else:
        print(f"\n    ⚠ UNEXPECTED: {lines[0]}")
    
except Exception as e:
    print(f"    ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("NEXT STEPS:")
print("=" * 70)
print("""
1. Check Flask terminal output when you run this test
   - Look for: "WebSocket request at /websockify"
   - Look for: "wsgi.websocket object is available" or "NOT available"

2. If you see "NOT available":
   - Apache is using ws:// protocol which doesn't work
   - Update apache.conf to use: ProxyPass / http://... upgrade=any
   - Reload Apache: sudo systemctl reload apache2

3. If you see "502 Bad Gateway" or "307 Redirect":
   - Same issue - Apache ws:// protocol problem
   - Use upgrade=any parameter

4. If you see "101 Switching Protocols":
   - Flask WebSocket is working!
   - Problem is in Apache proxy setup
   - Check Apache logs on the proxy server
""")
