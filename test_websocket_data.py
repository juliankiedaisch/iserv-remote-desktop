#!/usr/bin/env python3
"""
WebSocket Data Transfer Test

Tests if data can actually flow through the WebSocket connection.
This will reveal if the connection breaks after the handshake.
"""

import socket
import ssl
import base64
import os
import struct
import time

PROXY_HOST = "desktop.hub.mdg-hamburg.de"
PROXY_PORT = 443
TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"

print("=" * 70)
print("WEBSOCKET DATA TRANSFER TEST")
print("=" * 70)

def create_websocket_frame(data, opcode=0x1):
    """Create a WebSocket frame (text frame by default)"""
    payload = data.encode() if isinstance(data, str) else data
    payload_len = len(payload)
    
    # Frame header
    frame = bytearray()
    frame.append(0x80 | opcode)  # FIN + opcode
    
    # Payload length and mask bit
    if payload_len <= 125:
        frame.append(0x80 | payload_len)  # Mask bit + length
    elif payload_len <= 65535:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", payload_len))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", payload_len))
    
    # Masking key
    mask_key = os.urandom(4)
    frame.extend(mask_key)
    
    # Masked payload
    masked_payload = bytearray(payload)
    for i in range(len(masked_payload)):
        masked_payload[i] ^= mask_key[i % 4]
    frame.extend(masked_payload)
    
    return bytes(frame)

print("\n[1] Establishing WebSocket connection...")

try:
    context = ssl.create_default_context()
    
    with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=PROXY_HOST) as ssock:
            ws_key = base64.b64encode(os.urandom(16)).decode()
            
            # Send upgrade request
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
            
            ssock.sendall(request.encode())
            
            # Read response
            ssock.settimeout(5)
            response = b''
            
            while b'\r\n\r\n' not in response:
                chunk = ssock.recv(1024)
                if not chunk:
                    print("    ✗ Connection closed during handshake")
                    exit(1)
                response += chunk
            
            status_line = response.split(b'\r\n')[0].decode()
            
            if '101' not in status_line:
                print(f"    ✗ Handshake failed: {status_line}")
                exit(1)
            
            print("    ✓ WebSocket handshake successful")
            
            # Now try to receive data from the container
            print("\n[2] Waiting for data from container...")
            print("    (VNC server should send RFB protocol version)")
            
            ssock.settimeout(3)
            
            try:
                # Read WebSocket frame header
                header = ssock.recv(2)
                
                if not header:
                    print("    ✗ Connection closed immediately after handshake")
                    print("    → This is the Error 1005 issue!")
                    print("    → Flask is closing the connection after upgrade")
                    print("\n    REASON: Flask cannot connect to the container")
                    print(f"    → Check if container on port 7000 is accessible")
                    exit(1)
                
                fin = (header[0] & 0x80) != 0
                opcode = header[0] & 0x0F
                masked = (header[1] & 0x80) != 0
                payload_len = header[1] & 0x7F
                
                print(f"    ✓ Received WebSocket frame:")
                print(f"      FIN: {fin}, Opcode: {opcode}, Length: {payload_len}")
                
                if opcode == 0x8:  # Close frame
                    print("    ✗ Server sent close frame")
                    # Read close code
                    if payload_len >= 2:
                        close_data = ssock.recv(payload_len)
                        close_code = struct.unpack(">H", close_data[:2])[0]
                        close_reason = close_data[2:].decode('utf-8', errors='ignore')
                        print(f"      Close code: {close_code}")
                        print(f"      Reason: {close_reason if close_reason else 'No reason'}")
                        
                        if close_code == 1011:
                            print("\n    DIAGNOSIS: Close code 1011 = Server Error")
                            print("    → Flask encountered an error while proxying")
                            print("    → Most likely: Cannot connect to container")
                            print(f"    → Check Flask logs")
                            print(f"    → Verify container is running and accessible")
                    exit(1)
                
                if opcode == 0x1 or opcode == 0x2:  # Text or binary
                    # Read payload
                    if payload_len == 126:
                        payload_len = struct.unpack(">H", ssock.recv(2))[0]
                    elif payload_len == 127:
                        payload_len = struct.unpack(">Q", ssock.recv(8))[0]
                    
                    if masked:
                        mask_key = ssock.recv(4)
                    
                    payload = ssock.recv(min(payload_len, 1024))
                    
                    print(f"    ✓ Received {len(payload)} bytes of data")
                    print(f"      First bytes: {payload[:50]}")
                    
                    print("\n    ✓✓✓ SUCCESS! Data is flowing through WebSocket")
                    print("        The WebSocket proxy is working correctly!")
                    
            except socket.timeout:
                print("    ⚠ Timeout waiting for data")
                print("    → Connection is open but no data received")
                print("    → Flask may be waiting for container to respond")
                print("    → Or container is not sending data")
                
            except Exception as e:
                print(f"    ✗ Error reading data: {e}")
                import traceback
                traceback.print_exc()
                
except Exception as e:
    print(f"    ✗ Connection failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("""
If connection closed immediately after handshake:
  → Flask successfully upgraded to WebSocket
  → But then closed it immediately
  → This means Flask cannot connect to the container
  → Check: Is container running and accessible on its port?
  
If you got close code 1011:
  → Server error in Flask
  → Check Flask logs for the specific error
  → Most likely: container connection failed

If you received data:
  → Everything is working perfectly!
  → Browser issue or cookie/session problem
""")
