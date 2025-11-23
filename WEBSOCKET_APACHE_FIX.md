# WebSocket Connection Fix: Apache Not Forwarding Upgrade Requests to Flask

## Problem Description

WebSocket connections were failing with code 1005 ("Connection closed") even though Apache was successfully performing the WebSocket upgrade (HTTP 101 Switching Protocols). The issue was that Flask's WebSocket handler was never being called - the debug points in `proxy_websocket_root()` and `_proxy_websocket_with_eventlet()` were not triggering.

### Symptoms

1. **Browser Console Error**:
   ```
   Failed when connecting: Connection closed (code: 1005)
   ```

2. **Apache Debug Logs** (showing Apache trying to establish WebSocket to Flask):
   ```
   [proxy:debug] AH00944: connecting ws://172.22.0.27:5020/websockify to 172.22.0.27:5020
   [proxy:debug] AH00947: connecting /websockify to 172.22.0.27:5020 (172.22.0.27:5020)
   ```

3. **Flask Logs**: No WebSocket-related logs at all - the requests never reached Flask's handlers

## Root Cause

The Apache configuration was using **incorrect WebSocket proxying methods** that prevented Flask from receiving the WebSocket upgrade requests:

### Problem 1: Using `ws://` in RewriteRule

**Old Configuration**:
```apache
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteRule /(.*) ws://localhost:5020/$1 [P,L]
```

When using `ws://` protocol in the RewriteRule, Apache tries to:
1. Accept the WebSocket upgrade from the browser
2. Establish a **new WebSocket connection** to the backend
3. Proxy WebSocket frames between the two connections

This approach has critical issues:
- Flask with gevent-websocket **expects to receive an HTTP request** with `Upgrade: websocket` header
- Flask needs to inspect the HTTP headers (Referer, session, etc.) to determine which container to route to
- By the time Apache establishes a WebSocket connection to Flask, all the HTTP headers are lost
- Flask's WebSocket handler never gets called because it's not receiving an HTTP upgrade request

### Problem 2: Using `upgrade=websocket` in ProxyPass

**Old Configuration**:
```apache
ProxyPass / http://localhost:5020/ retry=3 timeout=3600 upgrade=websocket
```

The `upgrade=websocket` parameter tells Apache to automatically handle WebSocket upgrades for **all routes**. This causes Apache to:
1. Intercept any request with `Upgrade: websocket` header
2. Handle the upgrade at the Apache level
3. Try to establish a WebSocket connection to the backend

Again, this prevents Flask from receiving the original HTTP upgrade request with all necessary headers.

## How Flask WebSocket Handling Works

Flask with gevent-websocket uses this approach:

1. **Client sends HTTP request** with headers:
   ```
   GET /websockify HTTP/1.1
   Host: domain.com
   Upgrade: websocket
   Connection: Upgrade
   Sec-WebSocket-Key: ...
   Referer: https://domain.com/desktop/user-container
   ```

2. **Apache should forward this as-is** to Flask (as an HTTP request, not WebSocket)

3. **Flask receives HTTP request** with Upgrade header

4. **gevent-websocket middleware** detects the Upgrade header and:
   - Performs the WebSocket handshake
   - Upgrades the connection to WebSocket
   - Adds `wsgi.websocket` object to `request.environ`

5. **Flask handler** (`proxy_websocket_root()`) receives the request:
   - Can inspect all HTTP headers (Referer, session cookies, etc.)
   - Determines which container to proxy to
   - Uses the `wsgi.websocket` object to handle WebSocket communication

## Solution

### Change 1: Fix RewriteRule to Use `http://` Instead of `ws://`

**New Configuration**:
```apache
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteRule /(.*) http://localhost:5020/$1 [P,L]
```

By using `http://` instead of `ws://`, Apache:
- Forwards the HTTP request with `Upgrade: websocket` header to Flask as-is
- Does NOT try to establish a WebSocket connection itself
- Lets Flask's gevent-websocket handle the upgrade

### Change 2: Remove `upgrade=websocket` from ProxyPass

**New Configuration**:
```apache
ProxyPass / http://localhost:5020/ retry=3 timeout=3600
ProxyPassReverse / http://localhost:5020/
```

By removing `upgrade=websocket`:
- Apache doesn't intercept WebSocket upgrades automatically
- The RewriteRule handles WebSocket requests explicitly
- Flask receives all WebSocket upgrade requests properly

## Updated Apache Configuration

**File**: `apache.conf`

```apache
<VirtualHost *:443>
    ServerName your-domain.com
    
    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /path/to/your/certificate.crt
    SSLCertificateKeyFile /path/to/your/private.key
    
    # Modern SSL configuration
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite HIGH:!aNULL:!MD5
    SSLHonorCipherOrder on
    
    # Proxy settings for Flask application on port 5020
    ProxyPreserveHost On
    
    # Increase timeouts for long-running desktop connections
    Timeout 3600
    ProxyTimeout 3600
    
    # Keep-alive settings for better connection handling
    KeepAlive On
    MaxKeepAliveRequests 100
    KeepAliveTimeout 5
    
    # WebSocket support - CRITICAL for noVNC
    # DO NOT use upgrade=websocket in ProxyPass as it causes Apache to handle the upgrade
    # itself and prevents Flask from receiving the original HTTP upgrade request.
    # Flask needs to see the upgrade request to inspect Referer/session headers for routing.
    
    # RewriteRule handles WebSocket upgrade requests by passing them to Flask as-is
    # Flask's gevent-websocket will see the Upgrade header and handle the upgrade
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule /(.*) http://localhost:5020/$1 [P,L]
    
    # General proxy for all non-WebSocket HTTP routes
    # DO NOT add upgrade=websocket here - it breaks Flask's WebSocket handling
    ProxyPass / http://localhost:5020/ retry=3 timeout=3600
    ProxyPassReverse / http://localhost:5020/
    
    # Headers for proper proxying
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    
    # Logging
    ErrorLog ${APACHE_LOG_DIR}/iserv-remote-desktop-error.log
    CustomLog ${APACHE_LOG_DIR}/iserv-remote-desktop-access.log combined
</VirtualHost>

# Redirect HTTP to HTTPS
<VirtualHost *:80>
    ServerName your-domain.com
    Redirect permanent / https://your-domain.com/
</VirtualHost>
```

## How the Fix Works

### Request Flow After Fix

```
1. Browser → Apache:
   GET wss://domain.com/websockify HTTP/1.1
   Upgrade: websocket
   Connection: Upgrade
   Referer: https://domain.com/desktop/user-container
   
2. Apache → Flask:
   GET http://localhost:5020/websockify HTTP/1.1
   Upgrade: websocket
   Connection: Upgrade
   Referer: https://domain.com/desktop/user-container
   (All headers preserved as HTTP request)
   
3. Flask receives HTTP request:
   - proxy_websocket_root() handler is called
   - Function inspects Referer header
   - Determines container from Referer or session
   - gevent-websocket detects Upgrade header
   
4. gevent-websocket upgrades connection:
   - Performs WebSocket handshake
   - Adds wsgi.websocket to request.environ
   - Connection is now WebSocket
   
5. Flask proxies to container:
   - _proxy_websocket_with_eventlet() is called
   - Opens WebSocket connection to container
   - Bidirectional proxy established
```

## Why This Approach is Necessary

### Multi-Server Architecture

The application uses a multi-tier architecture:

```
SERVER 1 (Apache)              SERVER 2 (Docker Host)
┌────────────────┐            ┌─────────────────────┐
│    Browser     │            │  Container 1 (7001) │
│       ↓        │            │  Container 2 (7002) │
│    Apache      │  Network   │  Container 3 (7005) │
│   (Port 443)   │ =========> │  Container N (700X) │
└────────────────┘            └─────────────────────┘
         ↓
SERVER 1 or 3 (Flask)
┌────────────────┐
│  Flask App     │
│  (Port 5020)   │
│  - Routes      │
│  - Database    │
│  - Auth        │
└────────────────┘
```

Flask **must** be in the middle because:

1. **Dynamic Port Mapping**: Each container runs on a different port (7000-8000). Flask queries the database to determine: `username + desktop_type → container_id → host_port`

2. **Multi-User Routing**: Multiple users accessing different containers simultaneously. Apache has no knowledge of which container belongs to which user.

3. **Session/Authentication**: Flask validates that the user has permission to access the requested container via session and database checks.

4. **Physical Server Separation**: Apache and containers may be on different physical servers. Flask bridges the network connection.

5. **Header Inspection**: Flask needs to inspect HTTP headers (Referer, session cookies) to determine routing, which is impossible if Apache already upgraded to WebSocket.

### Why gevent-websocket Expects HTTP

gevent-websocket is designed as WSGI middleware that:
1. Intercepts HTTP requests with `Upgrade: websocket` header
2. Performs the WebSocket handshake according to RFC 6455
3. Provides the upgraded WebSocket object to the Flask handler

This design allows Flask to:
- Inspect all HTTP headers before upgrading
- Perform authentication/authorization
- Determine routing based on headers
- Only upgrade after validation

If Apache handles the upgrade, Flask loses all this capability.

## Testing the Fix

### 1. Update Apache Configuration

```bash
# Edit Apache config
sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf

# Test configuration
sudo apache2ctl configtest

# Reload Apache
sudo systemctl reload apache2
```

### 2. Check Apache Modules

```bash
# Ensure required modules are enabled
apache2ctl -M | grep proxy
# Should show:
#  proxy_module (shared)
#  proxy_http_module (shared)
#  proxy_wstunnel_module (shared)
```

### 3. Test WebSocket Connection

1. Start a container and wait 10-15 seconds
2. Access the desktop page
3. Open browser DevTools → Console
4. Look for Flask logs:

```bash
docker-compose logs -f app | grep websockify
```

**Expected logs after fix**:
```
[INFO] WebSocket request at /websockify with Referer: https://domain/desktop/user-container
[INFO] WebSocket upgrade request detected
[INFO] wsgi.websocket object is available
[DEBUG] Found container from Referer: user-container
[INFO] Proxying WebSocket to container container_name on port 7001
[INFO] Attempting to connect to container at localhost:7001
[INFO] Successfully connected to container port 7001
[INFO] WebSocket upgrade successful, starting bidirectional proxy
```

### 4. Verify No Code 1005 Error

In browser DevTools → Network → WS:
- WebSocket connection to `/websockify` should show `101 Switching Protocols`
- Connection should stay open (green indicator, shown as "pending")
- No immediate close with code 1005

## Troubleshooting

### Issue: Still Getting "Connection closed (code: 1005)"

**Check 1: Verify Apache Configuration**
```bash
# Check that RewriteRule uses http:// not ws://
sudo grep -A 2 "RewriteRule" /etc/apache2/sites-available/iserv-remote-desktop.conf

# Should show:
# RewriteRule /(.*) http://localhost:5020/$1 [P,L]
```

**Check 2: Verify ProxyPass Doesn't Have upgrade=websocket**
```bash
sudo grep "ProxyPass" /etc/apache2/sites-available/iserv-remote-desktop.conf

# Should NOT contain "upgrade=websocket"
# Should show:
# ProxyPass / http://localhost:5020/ retry=3 timeout=3600
```

**Check 3: Verify Flask is Receiving Requests**
```bash
# Check Flask logs for WebSocket requests
docker-compose logs -f app | grep -i "websocket request"

# If you see no logs, Apache is not forwarding requests to Flask
```

### Issue: Flask Logs Show "wsgi.websocket object is NOT available"

This means gevent-websocket is not handling the upgrade. Verify:

```bash
# Check gunicorn worker class
docker-compose exec app ps aux | grep gunicorn

# Should show:
# gunicorn ... --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker
```

If not using the correct worker:
```bash
# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

## Files Modified

1. **apache.conf**:
   - Changed RewriteRule from `ws://` to `http://`
   - Removed `upgrade=websocket` from ProxyPass
   - Added detailed comments explaining why

2. **APACHE_SETUP.md**:
   - Updated troubleshooting documentation
   - Corrected example configurations
   - Added notes about `http://` vs `ws://`

3. **WEBSOCKET_APACHE_FIX.md** (this file):
   - Comprehensive documentation of the issue and fix

## Related Documentation

- [WEBSOCKET_CONNECTION_FIX.md](WEBSOCKET_CONNECTION_FIX.md) - Previous WebSocket error handling fixes
- [APACHE_SETUP.md](APACHE_SETUP.md) - Complete Apache setup guide
- [WEBSOCKET_FIX.md](WEBSOCKET_FIX.md) - Original WebSocket implementation

## Summary

The fix changes Apache's WebSocket proxying from:
- ❌ Apache handles upgrade, establishes WebSocket to Flask
- ❌ Flask never sees HTTP headers, can't route properly

To:
- ✅ Apache forwards HTTP upgrade request to Flask as-is
- ✅ Flask's gevent-websocket handles upgrade
- ✅ Flask can inspect headers and route to correct container

This is **essential** for the multi-user, multi-container architecture where Flask must determine routing based on HTTP headers before upgrading to WebSocket.
