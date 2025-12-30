#!/usr/bin/env python3
"""
Test WebSocket connection using SUBDOMAIN-based routing
This is the BEST solution - Host header is always sent!
"""

import socket
import ssl
import base64
import os

TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"

# Use subdomain format
SUBDOMAIN_HOST = f"{TEST_CONTAINER}.desktop.hub.mdg-hamburg.de"

print("=" * 70)
print("TESTING SUBDOMAIN-BASED WEBSOCKET ROUTING")
print("=" * 70)
print(f"\nContainer: {TEST_CONTAINER}")
print(f"Subdomain URL: wss://{SUBDOMAIN_HOST}/websockify")
print("\nThis should work because:")
print("  ✓ Host header is ALWAYS sent (unlike Referer)")
print("  ✓ Wildcard SSL certificate covers *.desktop.hub.mdg-hamburg.de")
print("  ✓ No cookies needed")
print("  ✓ No special WebSocket config needed")
print("\n" + "=" * 70 + "\n")

try:
    context = ssl.create_default_context()
    
    with socket.create_connection((SUBDOMAIN_HOST, 443), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=SUBDOMAIN_HOST) as ssock:
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
            
            print(f"Sending WebSocket request to: {SUBDOMAIN_HOST}")
            print(f"Path: /websockify")
            print(f"Host header: {SUBDOMAIN_HOST}")
            
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
            
            print(f"\n{'=' * 70}")
            print(f"Response: {status}")
            print(f"{'=' * 70}\n")
            
            if '101' in status:
                print("✅ ✅ ✅  SUCCESS! ✅ ✅ ✅")
                print("\nSubdomain-based routing WORKS!")
                print("\nNext steps:")
                print("1. Deploy updated apache.conf with ServerAlias *.desktop.hub.mdg-hamburg.de")
                print("2. Update DNS to add wildcard A record: *.desktop.hub.mdg-hamburg.de")
                print("3. Configure noVNC in containers to use subdomain URLs:")
                print(f"   wss://{SUBDOMAIN_HOST}/websockify")
                print("\nNo more cookie/session issues! 🎉")
            else:
                print("❌ Failed")
                print(f"\nFull response:\n{response_str}")
                
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nThis is expected if:")
    print("  • DNS wildcard record not configured yet")
    print("  • Apache ServerAlias not deployed")
    print("\nTo fix:")
    print("1. Add DNS: *.desktop.hub.mdg-hamburg.de -> your server IP")
    print("2. Deploy apache.conf with ServerAlias *.desktop.hub.mdg-hamburg.de")
    print("3. Reload Apache: sudo systemctl reload apache2")
    import traceback
    traceback.print_exc()
