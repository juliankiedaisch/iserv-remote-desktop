#!/usr/bin/env python3
"""
Apache RewriteMap script to look up container targets from Flask API.
Receives subdomain, returns container IP:port or NULL.

NOTE: With the new nginx proxy architecture, this script is now OPTIONAL.
The nginx proxy in docker-compose handles subdomain routing through the backend.
However, this script can still be used if you prefer Apache to do direct routing.

Usage in Apache config:
RewriteMap containermap "prg:/path/to/get_container_target.py"
RewriteRule pattern ${containermap:%{HTTP_HOST}}
"""

import sys
import requests
from urllib.parse import quote

# Flask API configuration
# Update these to match your deployment
FLASK_API_URL = "http://172.22.0.27:8080/api/apache/container-target"
APACHE_API_KEY = "your-secure-random-key-here"  # Must match Flask APACHE_API_KEY

def get_container_target(subdomain):
    """
    Query Flask API for container target based on subdomain.
    
    Args:
        subdomain: Full hostname like "container-name.desktop.hub.mdg-hamburg.de"
    
    Returns:
        "IP:PORT" or "NULL" if not found
    """
    # Extract container proxy_path from subdomain
    # Format: desktop-{proxy-path}.hub.mdg-hamburg.de
    if not subdomain.startswith('desktop-') or not subdomain.endswith('.hub.mdg-hamburg.de'):
        return "NULL"
    
    # Remove 'desktop-' prefix and '.hub.mdg-hamburg.de' suffix
    proxy_path = subdomain.replace('desktop-', '').replace('.hub.mdg-hamburg.de', '')
    
    try:
        # Query Flask API
        response = requests.get(
            f"{FLASK_API_URL}/{quote(proxy_path)}",
            headers={"X-API-Key": APACHE_API_KEY},
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
