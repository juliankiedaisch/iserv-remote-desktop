#!/usr/bin/env python3
"""
Apache RewriteMap script to look up container targets from Flask API.
Receives subdomain, returns container IP:port or NULL.

Usage in Apache config:
RewriteMap containermap "prg:/path/to/get_container_target.py"
RewriteRule pattern ${containermap:%{HTTP_HOST}}
"""

import sys
import requests
import os
from urllib.parse import quote

# Flask API configuration
FLASK_API_URL = "http://172.22.0.27:5021/api/apache/container-target"
APACHE_API_KEY = os.environ.get('APACHE_API_KEY', 'lFSSwVI4bzjY5XJuEWAVXB')  # Match production key

def get_container_target(subdomain):
    """
    Query Flask API for container target based on subdomain.
    
    Args:
        subdomain: Full hostname like "desktop-{proxy}.hub.mdg-hamburg.de" or "audio-{proxy}.hub.mdg-hamburg.de"
    
    Returns:
        "IP:PORT" or "NULL" if not found
    """
    # Extract container proxy_path and type from subdomain
    # Formats:
    #   desktop-{proxy}.hub.mdg-hamburg.de → VNC port
    #   audio-{proxy}.hub.mdg-hamburg.de → Audio port
    #   test-desktop-{proxy}.hub.mdg-hamburg.de → VNC port (test env)
    #   test-audio-{proxy}.hub.mdg-hamburg.de → Audio port (test env)
    # Note: proxy_path uses dashes for DNS compatibility, but database has dots
    
    if not subdomain.endswith('.hub.mdg-hamburg.de'):
        return "NULL"
    
    # Determine if it's audio or desktop, and extract proxy_path
    port_type = 'vnc'  # default
    if subdomain.startswith('test-audio-'):
        proxy_path = subdomain.replace('test-audio-', '').replace('.hub.mdg-hamburg.de', '')
        port_type = 'audio'
    elif subdomain.startswith('audio-'):
        proxy_path = subdomain.replace('audio-', '').replace('.hub.mdg-hamburg.de', '')
        port_type = 'audio'
    elif subdomain.startswith('test-desktop-'):
        proxy_path = subdomain.replace('test-desktop-', '').replace('.hub.mdg-hamburg.de', '')
        port_type = 'vnc'
    elif subdomain.startswith('desktop-'):
        proxy_path = subdomain.replace('desktop-', '').replace('.hub.mdg-hamburg.de', '')
        port_type = 'vnc'
    else:
        return "NULL"
    
    try:
        # Query Flask API with port type parameter
        response = requests.get(
            f"{FLASK_API_URL}/{quote(proxy_path)}",
            headers={"X-API-Key": APACHE_API_KEY},
            params={"port_type": port_type},
            timeout=2
        )
        
        if response.status_code != 200:
            return "NULL"
        
        data = response.json()
        target = data.get('target')
        
        return target if target else "NULL"
        
    except Exception:
        return "NULL"

def main():
    """Read subdomains from stdin, write targets to stdout."""
    # Unbuffer output for Apache
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            subdomain = line.strip()
            target = get_container_target(subdomain)
            print(target, flush=True)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("NULL", flush=True)

if __name__ == '__main__':
    main()
