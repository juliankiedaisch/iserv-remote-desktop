#!/usr/bin/env python3
"""
Apache RewriteMap script to lookup container ports from database.
Reads container names from stdin, outputs IP:PORT to stdout.

Usage in Apache:
  RewriteMap container_lookup "prg:/path/to/get_container_port.py"
  RewriteRule ... ${container_lookup:%{HTTP_HOST}}
"""

import sys
import os
import subprocess
import json

# Flush output immediately for Apache
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

def get_container_info(container_name):
    """
    Query database for container IP and port.
    Returns "IP:PORT" or "NULL" if not found.
    """
    try:
        # Database connection info from environment
        db_cmd = [
            'psql',
            '-h', 'localhost',
            '-U', 'remote_desktop',
            '-d', 'remote_desktop',
            '-tA',  # Tuples only, no alignment
            '-c', f"SELECT host_port FROM containers WHERE proxy_path = '{container_name}' AND status = 'running' LIMIT 1;"
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = 'test_remote'
        
        result = subprocess.run(db_cmd, capture_output=True, text=True, env=env, timeout=2)
        
        if result.returncode == 0 and result.stdout.strip():
            port = result.stdout.strip()
            # Return localhost IP and port - Apache will proxy to this
            return f"172.22.0.27:{port}"
        
        return "NULL"
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return "NULL"

def main():
    """
    Read container names from stdin (one per line), output IP:PORT.
    This runs as a persistent process that Apache communicates with.
    """
    print("RewriteMap script started", file=sys.stderr)
    
    while True:
        try:
            # Read one line from Apache
            line = sys.stdin.readline()
            if not line:
                break
                
            container_name = line.strip()
            
            if not container_name:
                print("NULL")
                continue
            
            # Extract container name from subdomain format: julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de
            # We want just: julian-kiedaisch-ubuntu-vscode
            if '.' in container_name:
                # Take first part before first dot
                container_name = container_name.split('.')[0]
            
            result = get_container_info(container_name)
            print(result)
            
        except Exception as e:
            print(f"ERROR in main loop: {e}", file=sys.stderr)
            print("NULL")

if __name__ == "__main__":
    main()
