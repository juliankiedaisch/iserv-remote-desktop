#!/usr/bin/env python3
"""
Test if cookies are passed through Apache to Flask WebSocket
"""

import socket
import ssl
import base64
import os

PROXY_HOST = "desktop.hub.mdg-hamburg.de"
TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"

print("Testing if Flask receives cookies through Apache proxy...")
print()

# First, get a session cookie by accessing the desktop page
print("[1] Getting session cookie from desktop page...")

try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, 443), timeout=10) as sock:
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
                if len(response) > 10000:
                    break
            
            response_str = response.decode('utf-8', errors='ignore')
            
            # Extract Set-Cookie headers
            cookies = []
            for line in response_str.split('\r\n'):
                if line.startswith('Set-Cookie:'):
                    cookie = line.split('Set-Cookie:')[1].split(';')[0].strip()
                    cookies.append(cookie)
            
            if cookies:
                print(f"    ✓ Received {len(cookies)} cookie(s):")
                for cookie in cookies:
                    print(f"      {cookie[:80]}...")
            else:
                print("    ⚠ No cookies received")
                print("    This means Flask is not setting session cookies")
                
except Exception as e:
    print(f"    ✗ Error: {e}")
    exit(1)

if not cookies:
    print("\n✗ Cannot test WebSocket without cookies")
    exit(1)

# Now try WebSocket with the cookie
print(f"\n[2] Testing WebSocket with session cookie...")

try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, 443), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=PROXY_HOST) as ssock:
            ws_key = base64.b64encode(os.urandom(16)).decode()
            
            cookie_header = "; ".join(cookies)
            
            request = (
                f"GET /websockify HTTP/1.1\r\n"
                f"Host: {PROXY_HOST}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"Cookie: {cookie_header}\r\n"
                f"Origin: https://{PROXY_HOST}\r\n"
                f"Referer: https://{PROXY_HOST}/desktop/{TEST_CONTAINER}\r\n"
                f"\r\n"
            )
            
            print(f"    Sending WebSocket request with cookie")
            
            ssock.sendall(request.encode())
            ssock.settimeout(3)
            
            response = b''
            while b'\r\n\r\n' not in response:
                chunk = ssock.recv(1024)
                if not chunk:
                    break
                response += chunk
            
            response_str = response.decode('utf-8', errors='ignore')
            status = response_str.split('\r\n')[0]
            
            print(f"    Response: {status}")
            
            if '101' in status:
                print("    ✓ WebSocket handshake successful WITH cookie!")
                print("\n→ This means cookies ARE working")
                print("→ The issue might be with the Referer header or session data")
            else:
                print(f"    ✗ Handshake failed even with cookie")
                
except Exception as e:
    print(f"    ✗ Error: {e}")

print("\n" + "=" * 70)
print("CONCLUSION:")
print("=" * 70)
print("""
If WebSocket succeeded with cookie:
  → Cookies are working
  → Problem is likely: noVNC in the container is not sending cookies
  → Solution: Configure noVNC to send credentials: true

If WebSocket failed even with cookie:
  → Session is not finding the container
  → Check Flask logs for "Container not found" message
  → Verify the container name in the session matches the running container
""")
