# WebSocket Connection Code 1005 Fix

## Problem Description

WebSocket connections to `/websockify` were successfully upgrading (HTTP 101) but immediately closing with code 1005 ("no status received"). This prevented noVNC from establishing a connection to the Kasm containers.

### Error in Browser Console
```
GET wss://desktop.hub.mdg-hamburg.de/websockify [HTTP/1.1 101 Switching Protocols 14ms]
Failed when connecting: Connection closed (code: 1005)
```

## Root Cause

The WebSocket proxy implementation had several issues:

1. **Improper HTTP Response Returns**: When errors occurred after the WebSocket was established (e.g., container connection failures), the code tried to return HTTP `Response` objects, which is invalid for an already-upgraded WebSocket connection.

2. **Missing Close Frames**: When errors occurred, the WebSocket was closed abruptly without sending a proper close frame with a status code, resulting in code 1005 ("no status received").

3. **Insufficient Error Handling**: Connection errors to containers weren't properly caught and logged, making debugging difficult.

4. **Apache Configuration Conflicts**: The Apache configuration had redundant WebSocket handling rules that could potentially conflict.

## Why Manual WebSocket Proxying is Necessary

### SSL Certificate Architecture

The application uses a multi-tier SSL architecture:

```
Browser                   Apache                    Flask                     Container
[Trusted Client]  -wss://->  [Let's Encrypt    -ws://->  [Localhost      -wss://->  [Kasm Self-Signed
                            Wildcard Cert]             No SSL]                      Certificate]
                            (Trusted)                                               (Untrusted)
```

**Key Points**:

1. **Public-Facing SSL (Trusted)**: 
   - Apache terminates SSL with Let's Encrypt wildcard certificate
   - Browser sees valid, trusted certificate
   - Connection: `wss://domain.com/websockify`

2. **Internal Communication (Unencrypted)**:
   - Apache to Flask is unencrypted localhost communication
   - No SSL needed for local communication
   - Connection: `ws://localhost:5020/websockify`

3. **Container SSL (Self-Signed)**:
   - Kasm containers use HTTPS with self-signed certificates
   - Flask must disable SSL verification for these connections
   - Connection: `wss://localhost:PORT/websockify` with `KASM_VERIFY_SSL=false`

### Why Flask Cannot Be Bypassed

Flask must be in the middle because:

1. **Multi-User Container Orchestration**: 
   - Multiple users accessing different containers simultaneously
   - Each user has their own container(s) for different desktop types
   - Example: `user1-ubuntu-vscode` on port 7001, `user2-chromium` on port 7005, etc.
   - Apache has no knowledge of which container belongs to which user

2. **Physical Server Separation**:
   - **CRITICAL**: Apache runs on a different physical server than the Docker containers
   - Apache cannot directly access container ports
   - Flask acts as the bridge between the Apache server and the Docker host
   - All container communication must go through Flask's dynamic routing

3. **Dynamic Port Mapping**: 
   - Each container runs on a different port (7000-8000 range)
   - Port assignment is dynamic and stored in the database
   - Flask performs database lookup: `username + desktop_type → container_id → host_port`
   - Apache cannot query the database or know which ports are in use

4. **SSL Certificate Handling**: Flask must connect to containers with SSL verification disabled (for self-signed certificates). This is safe because:
   - Containers are on localhost only (from Flask's perspective)
   - No network traffic leaves the Docker host
   - Public-facing SSL is still fully trusted (Let's Encrypt)

5. **Authentication & Authorization**: Flask validates that the user has permission to access the requested container via session and database checks.

6. **Session Management**: Flask tracks which container each user is connected to for proper routing of assets and WebSocket connections.

### Why Manual WebSocket Upgrade

The manual WebSocket upgrade implementation is necessary because:

1. **Cannot use standard HTTP proxy**: Standard proxying doesn't handle the SSL certificate mismatch between public (trusted) and container (self-signed).

2. **Must control SSL verification**: Flask needs to explicitly disable certificate verification when connecting to containers while maintaining security for public connections.

3. **WebSocket client libraries**: Most WebSocket client libraries don't integrate well with WSGI servers for bidirectional proxying.

## Solution

### 1. Fixed WebSocket Error Handling

**File**: `app/routes/proxy_routes.py`

#### Changes to `_proxy_websocket_with_eventlet()`:

**Before**:
```python
if b"101" not in response.split(b"\r\n")[0]:
    current_app.logger.error(f"Container did not accept WebSocket upgrade: {response[:200]}")
    ws.close()
    return Response("Container did not accept WebSocket connection", status=502)
```

**After**:
```python
if b"101" not in response.split(b"\r\n")[0]:
    current_app.logger.error(f"Container did not accept WebSocket upgrade: {response[:200]}")
    # Close the client WebSocket with a proper close frame
    try:
        ws.close(1002, "Container rejected connection")
    except:
        pass
    return
```

#### Key Improvements:

1. **Proper Close Frames**: All error conditions now close the WebSocket with appropriate status codes:
   - `1002`: Protocol error (container rejected connection)
   - `1009`: Message too big (handshake response too large)
   - `1011`: Internal error (server error, cannot connect to container)

2. **Connection Timeout**: Added 10-second timeout for initial container connection:
   ```python
   sock.settimeout(10)
   sock.connect(('localhost', container.host_port))
   ```

3. **Better Error Handling**: Separated connection errors from handshake errors:
   ```python
   try:
       sock.connect(('localhost', container.host_port))
       current_app.logger.info(f"Successfully connected to container port {container.host_port}")
   except Exception as connect_error:
       current_app.logger.error(f"Failed to connect to container port {container.host_port}: {connect_error}")
       try:
           ws.close(1011, "Cannot connect to container")
       except:
           pass
       return
   ```

4. **Removed Invalid Returns**: Removed all `return Response(...)` statements after WebSocket establishment:
   ```python
   # Old code
   return Response("", status=200)  # WRONG - WebSocket already closed
   
   # New code
   # Don't return an HTTP response after WebSocket is closed
   # The connection is already closed, just return None
   ```

5. **Enhanced Logging**: Added comprehensive INFO and DEBUG level logging:
   ```python
   current_app.logger.info(f"WebSocket request at /websockify with Referer: {referer}")
   current_app.logger.debug(f"Request headers: {dict(request.headers)}")
   current_app.logger.info("WebSocket upgrade request detected")
   current_app.logger.info(f"Attempting to connect to container at localhost:{container.host_port}")
   ```

6. **Traceback Logging**: Added full exception tracebacks for debugging:
   ```python
   except Exception as e:
       current_app.logger.error(f"Error in WebSocket proxy: {str(e)}")
       import traceback
       current_app.logger.error(f"Traceback: {traceback.format_exc()}")
   ```

### 2. Simplified Apache Configuration

**File**: `apache.conf`

**Before**:
```apache
RewriteEngine On

# Handle WebSocket connections with proper upgrade headers
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteCond %{HTTP:Connection} =upgrade [NC]
RewriteRule /(.*)           ws://localhost:5020/$1 [P,L]

# Handle normal HTTP requests
RewriteCond %{HTTP:Upgrade} !=websocket [NC]
RewriteRule /(.*)           http://localhost:5020/$1 [P,L]

# General proxy for all routes with WebSocket upgrade support
ProxyPass / http://localhost:5020/ retry=3 timeout=3600 upgrade=websocket
ProxyPassReverse / http://localhost:5020/
```

**After**:
```apache
# WebSocket support - CRITICAL for noVNC
# Using ProxyPass with upgrade=websocket to handle both HTTP and WebSocket traffic
# This is the recommended approach for Apache 2.4.47+ with mod_proxy_wstunnel

# Set required headers for WebSocket proxying
RewriteEngine On
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteRule /(.*) ws://localhost:5020/$1 [P,L]

# General proxy for all routes with WebSocket upgrade support
ProxyPass / http://localhost:5020/ retry=3 timeout=3600 upgrade=websocket
ProxyPassReverse / http://localhost:5020/
```

**Changes**:
- Removed redundant `Connection` check in RewriteCond
- Removed separate HTTP request handling (ProxyPass handles it)
- Simplified to avoid potential conflicts

## How the Fix Works

### SSL Certificate Flow Diagram

```
                    PHYSICAL SERVER 1                              PHYSICAL SERVER 2
                   (Apache Server)                                 (Docker Host)
┌─────────────────────────────────────────────┐     ┌──────────────────────────────────────────┐
│                                             │     │                                          │
│  ┌─────────────┐                            │     │  ┌──────────────┐  Port 7001            │
│  │   Browser   │                            │     │  │ Container 1  │  user1-ubuntu-vscode  │
│  │             │                            │     │  │ (Kasm)       │  Self-Signed Cert     │
│  └──────┬──────┘                            │     │  └──────────────┘                        │
│         │                                   │     │                                          │
│         │ wss://domain.com/websockify       │     │  ┌──────────────┐  Port 7002            │
│         │ (Let's Encrypt - TRUSTED)         │     │  │ Container 2  │  user1-chromium       │
│         │                                   │     │  │ (Kasm)       │  Self-Signed Cert     │
│         ▼                                   │     │  └──────────────┘                        │
│  ┌────────────────────────────────────┐    │     │                                          │
│  │           Apache                   │    │     │  ┌──────────────┐  Port 7005            │
│  │  - SSL Termination                 │    │     │  │ Container 3  │  user2-ubuntu-vscode  │
│  │  - Let's Encrypt Wildcard Cert     │    │     │  │ (Kasm)       │  Self-Signed Cert     │
│  │  - Port 443 → 5020                 │    │     │  └──────────────┘                        │
│  └──────┬─────────────────────────────┘    │     │                                          │
│         │                                   │     │  ┌──────────────┐  Port 7008            │
│         │ ws://localhost:5020/websockify    │     │  │ Container N  │  userN-desktop        │
│         │ (Unencrypted Localhost - SAFE)   │     │  │ (Kasm)       │  Self-Signed Cert     │
│         │                                   │     │  └──────────────┘                        │
│         ▼                                   │     │         ▲                                │
│  ┌────────────────────────────────────┐    │     │         │                                │
│  │           Flask App                │    │──────────────┼────────────────────────────────┤
│  │  - WebSocket Proxy                 │◄═══╡═════════════╪════════════════════════════════╡
│  │  - Dynamic Port Lookup             │    │             │  wss://dockerhost:PORT/websockify│
│  │  - Database Query:                 │    │             │  (SSL verify disabled)           │
│  │    * user1-ubuntu-vscode → 7001    │    │             │  Manual WebSocket Upgrade        │
│  │    * user1-chromium → 7002         │    │             │  with SSL Context                │
│  │    * user2-ubuntu-vscode → 7005    │    │             │  (verify_mode=CERT_NONE)         │
│  │    * userN-desktop → 7008          │    │             │                                │
│  │  - SSL Verification Disabled       │    │             └─────────────────────────────────┘
│  │  - Multi-User Session Management   │    │                                          │
│  └────────────────────────────────────┘    │                                          │
│                                             │                                          │
└─────────────────────────────────────────────┘                                          │
                                                                                         │
                    Network Connection Between Servers ═════════════════════════════════┘

Flow Summary:
1. Browser → Apache: Uses trusted Let's Encrypt cert (validated)
2. Apache → Flask: Forwards unencrypted WebSocket on localhost
3. Flask queries database: Looks up which container port for this user/desktop
4. Flask → Docker Host: Connects to specific container port over network
5. Manual WebSocket upgrade necessary because:
   - SSL certificate mismatch (trusted Let's Encrypt vs self-signed Kasm)
   - Physical server separation (Apache can't reach containers directly)
   - Dynamic multi-user routing (Apache doesn't know port mappings)
```

### Request Flow

1. **Browser → Apache**: WebSocket upgrade request to `wss://domain/websockify`
2. **Apache → Flask**: Proxies as `ws://localhost:5020/websockify` (via RewriteRule)
3. **Flask receives**: gevent-websocket provides `request.environ['wsgi.websocket']`
4. **Flask determines container**: From Referer header or session (dynamic port lookup)
5. **Flask connects to container**: Opens SSL socket to `localhost:<container_port>` with cert verification disabled
6. **Error handling**:
   - If connection fails: Send WebSocket close frame with code 1011
   - If handshake fails: Send WebSocket close frame with code 1002 or 1009
   - If successful: Start bidirectional proxy
7. **Normal operation**: Proxy data between client and container
8. **Connection ends**: Close both sockets, log completion, return (no HTTP response)

### WebSocket Close Codes Used

| Code | Meaning | When Used |
|------|---------|-----------|
| 1002 | Protocol Error | Container rejected the WebSocket connection |
| 1009 | Message Too Big | Handshake response exceeded 8KB limit |
| 1011 | Internal Error | Cannot connect to container or server error |

## Testing

### Development Testing

```bash
# Start the development server
python3 run.py

# The server will output:
# ======================================================================
# Starting IServ Remote Desktop with WebSocket support
# Server: gevent-websocket (development mode)
# Address: http://0.0.0.0:5020
# WebSocket support: ENABLED
# ======================================================================
```

### Production Testing

```bash
# Check if WebSocket modules are enabled in Apache
apache2ctl -M | grep proxy_wstunnel

# Check application logs
docker-compose logs -f app | grep websockify

# You should see:
# [INFO] WebSocket request at /websockify with Referer: https://domain/desktop/user-desktop
# [INFO] WebSocket upgrade request detected
# [INFO] wsgi.websocket object is available
# [INFO] Attempting to connect to container at localhost:XXXX
# [INFO] Successfully connected to container port XXXX
# [INFO] WebSocket upgrade successful, starting bidirectional proxy
```

### Manual Testing

```bash
# Test container accessibility (replace XXXX with container port)
curl -k -i https://localhost:XXXX/websockify

# Expected: Connection refused or timeout (normal - WebSocket endpoint)

# Test through Flask app (requires running container)
curl -i http://localhost:5020/websockify
# Expected: "This endpoint is for WebSocket connections only..."
```

### Browser Testing

1. Start a container and wait 10-15 seconds for it to be ready
2. Access the desktop page: `https://domain/desktop/username-desktoptype`
3. Open browser DevTools → Network tab → WS filter
4. Look for `/websockify` connection:
   - Status should be `101 Switching Protocols`
   - Connection should stay open (shown as "pending" with green indicator)
   - No immediate close with code 1005

## Troubleshooting

### Still Getting Code 1005?

1. **Check container is running**:
   ```bash
   docker ps | grep <username>
   ```

2. **Check container logs**:
   ```bash
   docker logs <container_name>
   ```
   Look for VNC server startup messages.

3. **Check Flask logs**:
   ```bash
   docker-compose logs -f app | grep -A 5 "websockify"
   ```
   Look for connection errors or handshake failures.

4. **Verify container port**:
   ```bash
   # Check database for container port
   docker-compose exec app python3 -c "
   from app import create_app, db
   from app.models.containers import Container
   app = create_app(False)
   with app.app_context():
       c = Container.query.filter_by(username='<username>').first()
       print(f'Port: {c.host_port if c else None}')
   "
   ```

5. **Test container WebSocket directly**:
   ```bash
   # Install wscat if needed: npm install -g wscat
   wscat -c wss://localhost:<container_port>/websockify --no-check
   ```
   If this fails, the container's WebSocket server isn't ready.

### Common Issues

#### "Failed to connect to container port"

**Symptom**: Flask logs show "Failed to connect to container port XXXX: [Errno 111] Connection refused"

**Cause**: Container isn't running or hasn't started the VNC server yet.

**Solution**:
- Wait 10-15 seconds after starting a container
- Check `docker ps` to verify container is running
- Check container logs for VNC server startup

#### "Container did not accept WebSocket upgrade"

**Symptom**: Flask logs show "Container did not accept WebSocket upgrade: HTTP/1.1 403 Forbidden..."

**Cause**: VNC authentication failed or container is rejecting the connection.

**Solution**:
- Verify `VNC_PASSWORD` environment variable is correct
- Check container VNC configuration
- Ensure `KASM_VERIFY_SSL=false` for self-signed certificates

#### "wsgi.websocket object is NOT available"

**Symptom**: Flask logs show "wsgi.websocket object is NOT available (may be handled by Apache)"

**Cause**: Flask is not running with gevent-websocket worker.

**Solution**:
- Check `entrypoint.sh` has `GeventWebSocketWorker`
- Check `run.py` uses `WebSocketHandler`
- Restart the application

## Verification

After applying the fix, verify:

- [ ] WebSocket connections show status `101 Switching Protocols`
- [ ] Connections stay open (no immediate close)
- [ ] No code 1005 errors in browser console
- [ ] Flask logs show "WebSocket upgrade successful"
- [ ] noVNC display loads and shows desktop

## Files Modified

1. `app/routes/proxy_routes.py` - WebSocket proxy error handling
2. `apache.conf` - Simplified Apache configuration
3. `APACHE_SETUP.md` - Added troubleshooting section
4. `WEBSOCKET_CONNECTION_FIX.md` - This document

## Related Documentation

- [WEBSOCKET_FIX.md](WEBSOCKET_FIX.md) - Original WebSocket implementation
- [PROXY_FIXES.md](PROXY_FIXES.md) - Proxy routing fixes
- [APACHE_SETUP.md](APACHE_SETUP.md) - Apache configuration guide
