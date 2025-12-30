#!/usr/bin/env python3
"""
Test the current subdomain setup to diagnose where the issue is
"""

import socket
import ssl
import base64
import os

TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"
SUBDOMAIN_HOST = f"{TEST_CONTAINER}.desktop.hub.mdg-hamburg.de"

print("=" * 70)
print("DIAGNOSING SUBDOMAIN SETUP")
print("=" * 70)

print(f"\n1. Testing DNS resolution...")
try:
    ip = socket.gethostbyname(SUBDOMAIN_HOST)
    print(f"   ✓ {SUBDOMAIN_HOST} resolves to {ip}")
except Exception as e:
    print(f"   ✗ DNS failed: {e}")
    exit(1)

print(f"\n2. Testing HTTPS connection...")
try:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Accept self-signed certs
    
    with socket.create_connection((SUBDOMAIN_HOST, 443), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=SUBDOMAIN_HOST) as ssock:
            print(f"   ✓ HTTPS connection established")
            
            print(f"\n3. Testing WebSocket upgrade...")
            ws_key = base64.b64encode(os.urandom(16)).decode()
            
            request = (
                f"GET /websockify HTTP/1.1\r\n"
                f"Host: {SUBDOMAIN_HOST}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"Origin: https://{SUBDOMAIN_HOST}\r\n"
                f"\r\n"
            )
            
            ssock.sendall(request.encode())
            ssock.settimeout(3)
            
            response = b''
            while b'\r\n\r\n' not in response:
                chunk = ssock.recv(1024)
                if not chunk:
                    break
                response += chunk
            
            response_str = response.decode('utf-8', errors='ignore')
            status_line = response_str.split('\r\n')[0]
            
            print(f"   Response: {status_line}")
            
            if '101' in status_line:
                print(f"   ✓ WebSocket upgrade successful!")
                print(f"\n{'=' * 70}")
                print("✅ SUBDOMAIN ROUTING WORKS!")
                print("The issue must be in the noVNC client or container")
            else:
                print(f"   ✗ WebSocket upgrade failed")
                print(f"\nFull response:")
                print(response_str)
                print(f"\n{'=' * 70}")
                print("❌ ISSUE FOUND:")
                
                if '404' in status_line:
                    print("   • Apache doesn't recognize the subdomain")
                    print("   • Deploy apache.conf with ServerAlias *.desktop.hub.mdg-hamburg.de")
                elif '502' in status_line or '503' in status_line:
                    print("   • Apache can't reach Flask backend")
                    print("   • Check Flask is running on 172.22.0.27:5020")
                elif 'Forbidden' in status_line or '403' in status_line:
                    print("   • Apache is blocking the request")
                else:
                    print("   • Flask can't find the container from subdomain")
                    print("   • Check Flask logs for 'Container not found'")
                
except Exception as e:
    print(f"   ✗ Connection failed: {e}")
    print(f"\n{'=' * 70}")
    print("❌ CONNECTION FAILED:")
    print("   • Check if Apache is configured for *.desktop.hub.mdg-hamburg.de")
    print("   • SSL certificate might not cover subdomain")
    import traceback
    traceback.print_exc()
