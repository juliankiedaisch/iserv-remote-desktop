#!/usr/bin/env python3
"""
WebSocket Connection Testing Script

This script tests WebSocket connectivity at multiple levels to identify where the problem occurs.
"""

import sys
import os
import socket
import ssl
import base64
import time
from urllib.parse import urlparse

# Test 1: Check if Flask is running
print("=" * 70)
print("TEST 1: Check if Flask is listening on port 5020")
print("=" * 70)

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('localhost', 5020))
    sock.close()
    
    if result == 0:
        print("✓ Flask is listening on localhost:5020")
    else:
        print("✗ Flask is NOT listening on localhost:5020")
        print("  Please start Flask: python run.py")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error checking Flask: {e}")
    sys.exit(1)

# Test 2: Check database for containers
print("\n" + "=" * 70)
print("TEST 2: Check database for running containers")
print("=" * 70)

try:
    # Add the app directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from app import create_app, db
    app = create_app(os.environ.get('DEBUG', 'False'))
    
    with app.app_context():
        from app.models.containers import Container
        containers = Container.query.filter_by(status='running').all()
        
        if not containers:
            print("✗ No running containers found in database")
            print("  Please start a container from the web UI first")
            sys.exit(1)
        
        print(f"✓ Found {len(containers)} running container(s):")
        for c in containers:
            print(f"  - {c.container_name}")
            print(f"    Proxy path: {c.proxy_path}")
            print(f"    Host port: {c.host_port}")
            print(f"    Status: {c.status}")
        
        # Use the first container for testing
        test_container = containers[0]
        container_port = test_container.host_port
        container_name = test_container.container_name
        proxy_path = test_container.proxy_path
        
except Exception as e:
    print(f"✗ Error accessing database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Check if container port is accessible
print("\n" + "=" * 70)
print(f"TEST 3: Check if container port {container_port} is accessible")
print("=" * 70)

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('localhost', container_port))
    sock.close()
    
    if result == 0:
        print(f"✓ Container is listening on localhost:{container_port}")
    else:
        print(f"✗ Container is NOT listening on localhost:{container_port}")
        print(f"  Container may not be running or port mapping is incorrect")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error checking container: {e}")
    sys.exit(1)

# Test 4: Test HTTP request to Flask
print("\n" + "=" * 70)
print("TEST 4: Test HTTP request to Flask")
print("=" * 70)

try:
    import requests
    response = requests.get('http://localhost:5020/', timeout=5)
    print(f"✓ Flask HTTP is working (status: {response.status_code})")
except Exception as e:
    print(f"✗ Flask HTTP request failed: {e}")
    sys.exit(1)

# Test 5: Test WebSocket handshake to Flask
print("\n" + "=" * 70)
print("TEST 5: Test WebSocket handshake to Flask /websockify endpoint")
print("=" * 70)

try:
    import http.client
    
    conn = http.client.HTTPConnection('localhost', 5020, timeout=10)
    
    # Generate WebSocket key
    ws_key = base64.b64encode(os.urandom(16)).decode()
    
    headers = {
        'Upgrade': 'websocket',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key': ws_key,
        'Sec-WebSocket-Version': '13',
        'Referer': f'https://desktop.hub.mdg-hamburg.de/desktop/{proxy_path}'
    }
    
    print(f"Sending WebSocket upgrade request to /websockify")
    print(f"Headers: {headers}")
    
    conn.request('GET', '/websockify', headers=headers)
    response = conn.getresponse()
    
    print(f"\nResponse status: {response.status} {response.reason}")
    print(f"Response headers:")
    for header, value in response.getheaders():
        print(f"  {header}: {value}")
    
    if response.status == 101:
        print("✓ WebSocket upgrade successful (HTTP 101)")
        print("  Flask's gevent-websocket is working correctly!")
    elif response.status == 502:
        print("✗ Got 502 Bad Gateway")
        print("  This indicates Flask doesn't have wsgi.websocket object")
        print("  Apache configuration issue - ws:// protocol doesn't work with gevent-websocket")
    elif response.status == 307:
        print("✗ Got 307 Redirect")
        location = response.getheader('Location')
        print(f"  Redirecting to: {location}")
        print("  Flask is trying to redirect instead of handling WebSocket")
    elif response.status == 404:
        print("✗ Got 404 Not Found")
        print("  Container or session not found")
        body = response.read().decode('utf-8', errors='ignore')
        print(f"  Response body: {body}")
    else:
        print(f"✗ Unexpected response: {response.status}")
        body = response.read().decode('utf-8', errors='ignore')[:500]
        print(f"  Response body: {body}")
    
    conn.close()
    
except Exception as e:
    print(f"✗ WebSocket handshake failed: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Test with websocket-client library
print("\n" + "=" * 70)
print("TEST 6: Test with websocket-client library (if available)")
print("=" * 70)

try:
    import websocket
    
    ws_url = f'ws://localhost:5020/websockify'
    print(f"Connecting to: {ws_url}")
    
    # Create WebSocket with headers
    ws = websocket.WebSocket()
    ws.settimeout(5)
    
    headers = [
        f'Referer: https://desktop.hub.mdg-hamburg.de/desktop/{proxy_path}'
    ]
    
    ws.connect(ws_url, header=headers)
    print("✓ WebSocket connection established!")
    
    # Try to receive data
    ws.settimeout(2)
    try:
        data = ws.recv()
        print(f"✓ Received data: {len(data)} bytes")
    except:
        print("  (No data received, but connection is open)")
    
    ws.close()
    print("✓ WebSocket connection closed cleanly")
    
except ImportError:
    print("⚠ websocket-client not installed, skipping")
    print("  Install with: pip install websocket-client")
except Exception as e:
    print(f"✗ WebSocket connection failed: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Check Apache logs (if accessible)
print("\n" + "=" * 70)
print("TEST 7: Check for recent Apache WebSocket logs")
print("=" * 70)

apache_log_paths = [
    '/var/log/apache2/desktop_error.log',
    '/var/log/httpd/desktop_error.log'
]

found_log = False
for log_path in apache_log_paths:
    if os.path.exists(log_path):
        print(f"Checking: {log_path}")
        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()
                # Get last 20 lines with 'websocket' in them
                ws_lines = [l for l in lines if 'websocket' in l.lower()][-20:]
                if ws_lines:
                    print(f"Recent WebSocket-related log entries:")
                    for line in ws_lines:
                        print(f"  {line.strip()}")
                    found_log = True
                else:
                    print("  No WebSocket-related entries found")
        except PermissionError:
            print(f"  ⚠ Permission denied (run as root to read Apache logs)")
        except Exception as e:
            print(f"  ⚠ Error reading log: {e}")
        break

if not found_log:
    print("⚠ Apache logs not accessible from this server")
    print("  (Apache may be on a different server)")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"""
Container being tested:
  - Name: {container_name}
  - Proxy path: {proxy_path}
  - Port: {container_port}

Next steps:
1. Check the Flask terminal output for WebSocket logs when you test
2. If Flask shows "WebSocket request at /websockify" but no wsgi.websocket,
   then Apache's ws:// protocol is the problem
3. Try the apache.conf with 'upgrade=any' parameter instead of 'ws://'
4. After updating Apache config, reload: sudo systemctl reload apache2
""")
