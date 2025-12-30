# WebSocket Apache Configuration Fix

## Problem
WebSocket connections were failing with errors 1006 and 1005 when accessing `wss://desktop.hub.mdg-hamburg.de/websockify`. The browser could not establish a WebSocket connection because Apache was not properly proxying WebSocket upgrade requests to Flask's gevent-websocket server.

**Errors observed:**
```
Error 1006: Firefox kann keine Verbindung zu dem Server unter wss://desktop.hub.mdg-hamburg.de/websockify aufbauen.
Error 1005: Connection closed (code: 1005) - No Status Received
```

## Root Cause
The Apache configuration was using various approaches (RewriteRule, conditional headers) that either:
1. **Didn't properly proxy WebSocket connections** - Using `ws://` in RewriteRule doesn't allow Flask's gevent-websocket to receive the `wsgi.websocket` object
2. **Caused connection drops** - Flask received upgrade headers but no WebSocket object, leading to 307 redirects and connection closures
3. **Overly complex** - Multiple conditional rules that conflicted with each other

## Solution
Use Apache's native `upgrade=websocket` parameter in ProxyPass, which is specifically designed for WebSocket proxying. This simple, clean solution:
- Automatically detects WebSocket upgrade requests
- Properly forwards them to Flask while preserving the WebSocket connection
- Allows Flask's gevent-websocket handler to receive `wsgi.websocket` object
- Works with Apache 2.4.47+ and mod_proxy_wstunnel

## Updated Configuration
The key change in [apache.conf](apache.conf):

```apache
# WebSocket support - CRITICAL for noVNC
# ProxyPass with upgrade=websocket handles both HTTP and WebSocket traffic
# This allows Flask's gevent-websocket to properly receive WebSocket connections

# Frontend application with WebSocket support
# The "upgrade=websocket" parameter tells mod_proxy_wstunnel to handle WebSocket upgrades
ProxyPass / http://172.22.0.27:5020/ upgrade=websocket retry=3 timeout=3600
ProxyPassReverse / http://172.22.0.27:5020/
```

**That's it!** One ProxyPass directive with `upgrade=websocket` replaces all the RewriteRule and conditional header logic.

## Required Apache Modules
Ensure these modules are enabled on your Apache server:

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod proxy_wstunnel
sudo a2enmod rewrite
sudo a2enmod ssl
sudo a2enmod headers
```

## Deployment Steps

### On the Apache Proxy Server (desktop.hub.mdg-hamburg.de):

1. **Check Apache version (must be 2.4.47 or later):**
   ```bash
   apache2 -v
   ```
   The `upgrade=websocket` parameter requires Apache 2.4.47+

2. **Backup the current configuration:**
   ```bash
   sudo cp /etc/apache2/sites-available/desktop.conf /etc/apache2/sites-available/desktop.conf.backup
   ```

3. **Copy the updated configuration:**
   Copy the contents of `apache.conf` from this repository to your Apache configuration file:
   ```bash
   sudo nano /etc/apache2/sites-available/desktop.conf
   # Replace the ProxyPass lines with:
   # ProxyPass / http://172.22.0.27:5020/ upgrade=websocket retry=3 timeout=3600
   # ProxyPassReverse / http://172.22.0.27:5020/
   ```

4. **Verify required modules are enabled:**ssl headers
   ```
   Note: `mod_rewrite` is no longer needed with this approach

5  ```

4. **Test the configuration:**
   ```bash
   sudo apache2ctl configtest
   ```
   You should see: `Syntax OK`
6
5. **Reload Apache:**
   ```bash
   sudo systemctl reload apache2
   ```
   
   Or if a full restart is needed:
   ```bash
   sudo systemctl restart apache2
   ```

7. **Monitor the logs:**
   ```bash
   sudo tail -f /var/log/apache2/desktop_error.log
   sudo tail -f /var/log/apache2/desktop_access.log
   ```

## How It Works

### Request Flow:

1. **Browser** makes HTTPS request to `https://desktop.hub.mdg-hamburg.de/desktop/username-desktop`
2. **Apache** (Port 443) receives HTTPS request, proxies to Flask via HTTP
3. **Flask** (Port 5020) serves the noVNC page with JavaScript
4. **JavaScript** initiates WebSocket connection to `wss://desktop.hub.mdg-hamburg.de/websockify`
5. **Apache** detects `Upgrade: websocket` header (via `upgrade=websocket` parameter)
6. **Apache** tunnels the WebSocket upgrade through to Flask, preserving the connection
7. **Flask's gevent-websocket** receives the WebSocket in `wsgi.websocket` object
8. **Flask** proxies WebSocket to container (e.g., `wss://172.22.0.27:7001/websockify`)
9. **Container** (Kasm desktop) handles WebSocket connection for VNC

### Protocol Chain:
```
Browser (wss://)  →  Apache HTTPS (detects Upgrade header)
                  ↓  
Apache ProxyPass  →  Flask gevent-websocket (receives wsgi.websocket)
 (transparent tunnel)
                  ↓
Flask Proxy       →  Container (wss://172.22.0.27:PORT/websockify)
```

### Why This Works:
- **`upgrade=websocket`** tells Apache to tunnel WebSocket connections transparently
- Flask's **gevent-websocket** sees the connection as if it came directly from the client
- The `wsgi.websocket` object is properly populated in Flask's request.environ
- Flask can then proxy the WebSocket to the container using its built-in logic

## Verification

After deploying the configuration:

1. **Test regular HTTP access:**
   ```bash
   curl -I https://desktop.hub.mdg-hamburg.de/
   ```
   Should return HTTP 200 with HTML content

2. **Test WebSocket upgrade detection:**
   Check Apache logs after attempting a desktop connection
   ```bash
   sudo grep -i websocket /var/log/apache2/desktop_access.log
   ```

3. **Access desktop via browser:**
   - Navigate to `https://desktop.hub.mdg-hamburg.de`
   - Start a container
   - The desktop should now load with a working VNC connection

4. **Check browser console:**
   - Open browser developer tools (F12)
   - Go to Console tab
   - Should NOT see WebSocket connection errors
   - Should see successful WebSocket connection
wstunnel'
   ```
   Should show:
   - proxy_module
   - proxy_http_module
   - proxy_wstunnel_module

2. **Check Apache version:**
   ```bash
   apache2 -v
   ```
   Must be 2.4.47 or later for `upgrade=websocket` support

3  ```
   Look for: "Handling WebSocket with gevent-websocket" - this confirms Flask received the WebSocket

4  - proxy_module
   - proxy_http_module
   - proxy_wstunnel_module
   - rewrite_module

2. **Check Flask logs:**
5. **Test Flask WebSocket endpoint directly
   # On Docker host (172.22.0.27)
   # Check if WebSocket requests are reaching Flask
   tail -f /path/to/flask/logs
   ```

3. **Verify Flask is listening:**
   ```bash
   # On Docker host
   ss -tulpn | grep 5020
   ```
   Should show Flask listening on 0.0.0.0:5020

4. **Test direct Flask WebSocket:**
   ```bash
   # From Apache server
   curl -i -N \
     -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: test" \
     htt`upgrade=websocket` Parameter?
- **Native support**: Built into Apache 2.4.47+ specifically for WebSocket proxying
- **Automatic detection**: Apache automatically recognizes WebSocket upgrade requests
- **Transparent tunneling**: Connection is tunneled through to Flask without modification
- **Preserves WebSocket state**: Flask's gevent-websocket receives proper `wsgi.websocket` object
- **Simpler configuration**: One parameter replaces complex RewriteRule logic

### Why Not RewriteRule with ws://?
- RewriteRule with `ws://` protocol doesn't preserve the WebSocket object for Flask
- Flask's gevent-websocket needs the connection to come through as a proper WSGI WebSocket
- Using `ws://` in RewriteRule causes Flask to see upgrade headers but no `wsgi.websocket` object
- This leads to Flask returning HTTP redirects (307) which close the WebSocket connection (error 1005)

### Order of Operations (with upgrade=websocket):
1. Client sends HTTP request with `Upgrade: websocket` header
2. Apache sees `upgrade=websocket` parameter in ProxyPass
3. Apache establishes tunnel to Flask on port 5020
4. Flask's gevent-websocket handler receives full WebSocket in `request.environ['wsgi.websocket']`
5. Flask proxies the WebSocket to the container
6. Container responds through Flask back to client versions
- The RewriteRule approach is more explicit and easier to debug

### Order of Rules Matters
1. RewriteCond checks for WebSocket headers
2. If matched, RewriteRule proxies to `ws://` and stops ([L] flag)
3. If not matched, ProxyPass handles regular HTTP traffic

### Security Considerations
- SSL termination happens at Apache (Let's Encrypt certificate)
- Apache → Flask communication is unencrypted HTTP/WS on private network
- Flask → Container uses HTTPS/WSS with self-signed certificates
- SSL verification disabled for container connections (KASM_VERIFY_SSL=false)

## Additional Notes

- The Flask application on 172.22.0.27:5020 must be running with WebSocket support (gevent-websocket)
- Current Flask process: `python /root/iserv-remote-desktop/run.py` (PID 3472831)
- Flask uses geventwebsocket.handler.WebSocketHandler for WebSocket support
- Multiple containers can be accessed simultaneously via different proxy paths

## References

- Apache mod_proxy_wstunnel: https://httpd.apache.org/docs/2.4/mod/mod_proxy_wstunnel.html
- WebSocket Protocol RFC 6455: https://tools.ietf.org/html/rfc6455
- Flask WebSocket handling: [proxy_routes.py](app/routes/proxy_routes.py#L286)
