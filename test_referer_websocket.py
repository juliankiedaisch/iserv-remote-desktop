#!/usr/bin/env python3
"""
Test WebSocket WITHOUT cookie but WITH Referer header
"""

import socket
import ssl
import base64
import os

PROXY_HOST = "desktop.hub.mdg-hamburg.de"
TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"

print("Testing WebSocket WITHOUT cookie but WITH Referer...")

try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, 443), timeout=10) as sock:
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
            
            print(f"Sending WebSocket with Referer but NO cookie...")
            print(f"Referer: https://{PROXY_HOST}/desktop/{TEST_CONTAINER}")
            
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
            
            print(f"\nResponse: {status}")
            
            if '101' in status:
                print("✓✓✓ SUCCESS! WebSocket works with just Referer header!")
                print("\n→ Flask CAN find the container from Referer")
                print("→ The issue is that the BROWSER'S WebSocket is not sending Referer")
                print("→ This is a browser security feature")
                print("\nSOLUTION: Change the WebSocket URL in the container to include the path")
                print(f"  Instead of: wss://{PROXY_HOST}/websockify")
                print(f"  Use: wss://{PROXY_HOST}/desktop/{TEST_CONTAINER}/websockify")
            else:
                print("✗ Failed even with Referer")
                print(f"→ Flask cannot find container from Referer alone")
                
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
