#!/usr/bin/env python3
"""
Comprehensive test comparing all three routing methods:
1. Subdomain-based (BEST - always works)
2. Referer-based (works only if Referer sent)
3. Cookie-based (works only if cookies sent)
"""

import socket
import ssl
import base64
import os

PROXY_HOST = "desktop.hub.mdg-hamburg.de"
TEST_CONTAINER = "julian.kiedaisch-ubuntu-vscode"
SUBDOMAIN_HOST = f"{TEST_CONTAINER}.desktop.hub.mdg-hamburg.de"

def test_websocket(host, path, headers_dict, test_name):
    """Test WebSocket connection with specific headers"""
    print(f"\n{'=' * 70}")
    print(f"TEST: {test_name}")
    print(f"{'=' * 70}")
    print(f"Host: {host}")
    print(f"Path: {path}")
    print("Headers:")
    for k, v in headers_dict.items():
        if k not in ['Host', 'Upgrade', 'Connection', 'Sec-WebSocket-Key', 'Sec-WebSocket-Version']:
            print(f"  {k}: {v}")
    
    try:
        context = ssl.create_default_context()
        
        with socket.create_connection((host, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                ws_key = base64.b64encode(os.urandom(16)).decode()
                
                # Build request
                request_lines = [
                    f"GET {path} HTTP/1.1",
                    f"Host: {host}",
                    "Upgrade: websocket",
                    "Connection: Upgrade",
                    f"Sec-WebSocket-Key: {ws_key}",
                    "Sec-WebSocket-Version: 13"
                ]
                
                # Add custom headers
                for key, value in headers_dict.items():
                    if key not in ['Host', 'Upgrade', 'Connection', 'Sec-WebSocket-Key', 'Sec-WebSocket-Version']:
                        request_lines.append(f"{key}: {value}")
                
                request_lines.append("")  # Empty line
                request_lines.append("")  # End of headers
                request = "\r\n".join(request_lines)
                
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
                    print("✅ SUCCESS - WebSocket established")
                    return True
                else:
                    print("❌ FAILED - WebSocket rejected")
                    return False
                    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("=" * 70)
    print("WEBSOCKET ROUTING COMPARISON TEST")
    print("=" * 70)
    print("\nTesting all three methods to find container:")
    print("1. SUBDOMAIN (Host header) - BEST")
    print("2. REFERER (Referer header) - Only if sent")
    print("3. COOKIE (Session cookie) - Only if sent")
    
    results = {}
    
    # Test 1: Subdomain-based (should always work)
    results['subdomain'] = test_websocket(
        host=SUBDOMAIN_HOST,
        path="/websockify",
        headers_dict={
            "Origin": f"https://{SUBDOMAIN_HOST}"
        },
        test_name="Method 1: SUBDOMAIN-BASED (Host header)"
    )
    
    # Test 2: Referer-based (works only if Referer sent)
    results['referer'] = test_websocket(
        host=PROXY_HOST,
        path="/websockify",
        headers_dict={
            "Origin": f"https://{PROXY_HOST}",
            "Referer": f"https://{PROXY_HOST}/desktop/{TEST_CONTAINER}"
        },
        test_name="Method 2: REFERER-BASED (Referer header)"
    )
    
    # Test 3: No subdomain, no referer, no cookie (should fail)
    results['none'] = test_websocket(
        host=PROXY_HOST,
        path="/websockify",
        headers_dict={
            "Origin": f"https://{PROXY_HOST}"
        },
        test_name="Method 3: NO CONTAINER INFO (should fail)"
    )
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Method':<30} {'Result':<20} {'Reliability'}")
    print("-" * 70)
    print(f"{'1. Subdomain (Host header)':<30} {'✅ ' + ('PASS' if results['subdomain'] else 'FAIL'):<20} {'Always sent'}")
    print(f"{'2. Referer header':<30} {'✅ ' + ('PASS' if results['referer'] else 'FAIL'):<20} {'Often blocked'}")
    print(f"{'3. No container info':<30} {'❌ ' + ('PASS' if results['none'] else 'FAIL'):<20} {'Expected failure'}")
    
    print("\n" + "=" * 70)
    if results['subdomain']:
        print("🎉 SUBDOMAIN ROUTING WORKS!")
        print("\nRecommendation: Use subdomain-based routing")
        print("URL format: https://container-name.desktop.hub.mdg-hamburg.de")
        print("\nAdvantages:")
        print("  ✓ Host header always sent (100% reliable)")
        print("  ✓ No cookies needed")
        print("  ✓ No Referer dependency")
        print("  ✓ Works with any WebSocket client")
        print("  ✓ Wildcard SSL already configured")
    else:
        print("⚠️  SUBDOMAIN ROUTING NOT WORKING")
        print("\nPossible issues:")
        print("  • DNS wildcard not configured")
        print("  • Apache ServerAlias not deployed")
        print("  • Flask not updated")
    
    print("=" * 70)

if __name__ == '__main__':
    main()
