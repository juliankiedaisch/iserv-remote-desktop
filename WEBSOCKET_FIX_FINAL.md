# WebSocket Fix Summary

## The Issue
WebSocket connections failing with error codes 1006 and 1005 when trying to connect to remote desktops.

## The Root Cause
Apache was not properly proxying WebSocket upgrade requests to Flask's gevent-websocket server. The previous configuration:
- Used commented-out or incorrect RewriteRule approaches
- Didn't preserve the WebSocket connection for Flask
- Caused Flask to return HTTP redirects instead of handling WebSockets

## The Solution
**Add `upgrade=websocket` parameter to ProxyPass directive in Apache configuration**

### One-Line Fix:
```apache
ProxyPass / http://172.22.0.27:5020/ upgrade=websocket retry=3 timeout=3600
```

That's it! This single parameter tells Apache to:
1. Detect WebSocket upgrade requests automatically
2. Tunnel them transparently to Flask
3. Preserve the WebSocket state so Flask's gevent-websocket can handle it properly

## Deployment

### On your Apache server (desktop.hub.mdg-hamburg.de):

1. **Edit the Apache config:**
   ```bash
   sudo nano /etc/apache2/sites-available/desktop.conf
   ```

2. **Find the ProxyPass line and add `upgrade=websocket`:**
   ```apache
   # Change from:
   ProxyPass / http://172.22.0.27:5020/ retry=3 timeout=3600
   
   # To:
   ProxyPass / http://172.22.0.27:5020/ upgrade=websocket retry=3 timeout=3600
   ```

3. **Test and reload:**
   ```bash
   sudo apache2ctl configtest
   sudo systemctl reload apache2
   ```

## Requirements
- **Apache 2.4.47+** (check with: `apache2 -v`)
- **mod_proxy_wstunnel** enabled (enable with: `sudo a2enmod proxy_wstunnel`)

## Verification
After deploying:
1. Open https://desktop.hub.mdg-hamburg.de
2. Start a desktop container
3. The VNC connection should now work without WebSocket errors

## Files Updated
- [apache.conf](apache.conf) - Contains the correct configuration
- [WEBSOCKET_APACHE_REWRITE_FIX.md](WEBSOCKET_APACHE_REWRITE_FIX.md) - Full technical documentation
- [WEBSOCKET_FIX_INSTRUCTIONS.sh](WEBSOCKET_FIX_INSTRUCTIONS.sh) - Quick reference guide

## Technical Details
The `upgrade=websocket` parameter enables Apache's mod_proxy_wstunnel to:
- Transparently tunnel WebSocket connections through to the backend
- Preserve the WebSocket protocol and headers
- Allow Flask's gevent-websocket to receive the proper `wsgi.websocket` object
- Handle both HTTP and WebSocket traffic through the same ProxyPass directive

This is the recommended approach for WebSocket proxying in modern Apache versions (2.4.47+).
