#!/usr/bin/env python3
"""
Comprehensive diagnostic to find the WebSocket 1005 error
"""

import socket
import ssl
import base64
import os
import subprocess
import json

print("=" * 70)
print("COMPREHENSIVE WEBSOCKET DIAGNOSTICS")
print("=" * 70)

# Step 1: Check running containers
print("\n[1] Checking running containers...")
result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}\t{{.Ports}}'], 
                       capture_output=True, text=True)
containers = [line for line in result.stdout.split('\n') if 'kasm' in line.lower()]

if not containers:
    print("   ✗ No Kasm containers running!")
    print("\n→ Go to https://desktop.hub.mdg-hamburg.de and start a desktop first")
    exit(1)

print(f"   ✓ Found {len(containers)} container(s):")
for container in containers:
    parts = container.split('\t')
    if len(parts) >= 2:
        name = parts[0]
        ports = parts[1]
        print(f"     - {name}")
        print(f"       Ports: {ports}")
        
        # Extract proxy_path from container name
        # Format: kasm-username-desktop-type-sessionid
        if 'kasm-' in name:
            parts = name.replace('kasm-', '').rsplit('-', 1)[0]  # Remove session ID
            proxy_path = parts
            print(f"       Expected proxy_path: {proxy_path}")
            
            # Extract port
            if '0.0.0.0:' in ports:
                port = ports.split('0.0.0.0:')[1].split('->')[0]
                print(f"       Port: {port}")
                
                # Step 2: Test direct connection to container
                print(f"\n[2] Testing direct connection to container on localhost:{port}...")
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex(('localhost', int(port)))
                    sock.close()
                    if result == 0:
                        print(f"   ✓ Container port {port} is accessible")
                    else:
                        print(f"   ✗ Container port {port} is not accessible")
                except Exception as e:
                    print(f"   ✗ Error: {e}")
                
                # Step 3: Test subdomain DNS
                subdomain = f"{proxy_path}.desktop.hub.mdg-hamburg.de"
                print(f"\n[3] Testing DNS for subdomain: {subdomain}")
                try:
                    ip = socket.gethostbyname(subdomain)
                    print(f"   ✓ Resolves to: {ip}")
                except Exception as e:
                    print(f"   ✗ DNS failed: {e}")
                    continue
                
                # Step 4: Test HTTPS to subdomain
                print(f"\n[4] Testing HTTPS connection to {subdomain}...")
                try:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    
                    with socket.create_connection((subdomain, 443), timeout=5) as sock:
                        with context.wrap_socket(sock, server_hostname=subdomain) as ssock:
                            print(f"   ✓ HTTPS connection established")
                            
                            # Step 5: Test WebSocket upgrade
                            print(f"\n[5] Testing WebSocket upgrade to wss://{subdomain}/websockify")
                            ws_key = base64.b64encode(os.urandom(16)).decode()
                            
                            request = (
                                f"GET /websockify HTTP/1.1\r\n"
                                f"Host: {subdomain}\r\n"
                                f"Upgrade: websocket\r\n"
                                f"Connection: Upgrade\r\n"
                                f"Sec-WebSocket-Key: {ws_key}\r\n"
                                f"Sec-WebSocket-Version: 13\r\n"
                                f"Origin: https://{subdomain}\r\n"
                                f"\r\n"
                            )
                            
                            print(f"   Sending WebSocket request...")
                            ssock.sendall(request.encode())
                            ssock.settimeout(3)
                            
                            response = b''
                            while b'\r\n\r\n' not in response:
                                chunk = ssock.recv(1024)
                                if not chunk:
                                    break
                                response += chunk
                            
                            response_str = response.decode('utf-8', errors='ignore')
                            headers = response_str.split('\r\n')
                            status = headers[0]
                            
                            print(f"   Response: {status}")
                            
                            if '101' in status:
                                print(f"   ✓ WebSocket upgrade successful!")
                                
                                # Step 6: Try to receive data
                                print(f"\n[6] Checking for WebSocket data...")
                                try:
                                    ssock.settimeout(2)
                                    data = ssock.recv(1024)
                                    if data:
                                        print(f"   ✓ Received {len(data)} bytes")
                                        # Check if it's a close frame (opcode 8)
                                        if len(data) >= 2:
                                            opcode = data[0] & 0x0F
                                            if opcode == 8:
                                                print(f"   ✗ SERVER SENT CLOSE FRAME!")
                                                if len(data) > 2:
                                                    close_code = int.from_bytes(data[2:4], 'big')
                                                    print(f"   Close code: {close_code}")
                                                    if close_code == 1011:
                                                        print(f"   → Flask couldn't find container")
                                                    elif close_code == 1006:
                                                        print(f"   → Abnormal closure")
                                            else:
                                                print(f"   ✓ Received data (opcode {opcode})")
                                    else:
                                        print(f"   ✗ No data received")
                                except socket.timeout:
                                    print(f"   ✗ Timeout waiting for data")
                                    print(f"   → Container might not be responding")
                            else:
                                print(f"   ✗ WebSocket upgrade failed")
                                print(f"\n   Full response:")
                                for header in headers[:10]:
                                    print(f"     {header}")
                                
                                if '404' in status:
                                    print(f"\n   → Apache doesn't recognize subdomain")
                                    print(f"   → Check apache.conf has ServerAlias *.desktop.hub.mdg-hamburg.de")
                                elif '502' in status or '503' in status:
                                    print(f"\n   → Apache can't reach Flask")
                                    print(f"   → Check Flask is running and accessible")
                                elif '403' in status:
                                    print(f"\n   → Forbidden - check Apache config")
                                
                except Exception as e:
                    print(f"   ✗ Error: {e}")
                    import traceback
                    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSTICS COMPLETE")
print("=" * 70)
