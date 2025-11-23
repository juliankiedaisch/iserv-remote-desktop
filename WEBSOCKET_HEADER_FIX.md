# WebSocket Header Forwarding Fix

## Problem Description

WebSocket connections were failing because Apache was not forwarding the WebSocket upgrade headers (`Upgrade` and `Connection`) to Flask. The logs showed:

```
[INFO] in proxy_routes: NOT a WebSocket upgrade request
```

This resulted in:
- Browser error: `Failed when connecting: Connection closed (code: 1006)`
- Flask not detecting the WebSocket upgrade request
- NoVNC failing to establish a connection

## Root Cause

When Apache uses `RewriteRule` with the `[P]` (proxy) flag, it internally uses `mod_proxy` to forward the request. However, `mod_proxy` **strips hop-by-hop headers by default**, including:
- `Upgrade`
- `Connection`
- `Keep-Alive`
- `Transfer-Encoding`
- `TE`
- `Trailer`
- `Proxy-Authorization`
- `Proxy-Authenticate`

These headers are considered "hop-by-hop" because they control the connection between the client and the proxy, not between the proxy and the backend server. However, for WebSocket upgrades to work properly with Flask's gevent-websocket, these headers **must be forwarded**.

## Solution

The fix explicitly preserves the `Upgrade` and `Connection` headers when proxying WebSocket requests using `SetEnvIf` to detect them:

### Updated Apache Configuration (Recommended)

```apache
# Detect WebSocket upgrade requests and set an environment variable
SetEnvIf Upgrade "(?i)websocket" IS_WEBSOCKET=1
SetEnvIf Connection "(?i)upgrade" IS_UPGRADE=1

# Preserve WebSocket headers for requests that have them
# mod_proxy strips hop-by-hop headers by default, but we need them for Flask
RequestHeader set Upgrade "websocket" env=IS_WEBSOCKET
RequestHeader set Connection "Upgrade" env=IS_UPGRADE

# General proxy for all routes (HTTP and WebSocket)
ProxyPass / http://localhost:5020/ retry=3 timeout=3600
ProxyPassReverse / http://localhost:5020/
```

### How It Works

1. **SetEnvIf**: Detects WebSocket upgrade requests by checking for `Upgrade: websocket` and `Connection: upgrade` headers (case-insensitive via `(?i)`)

2. **Environment Variables**:
   - `IS_WEBSOCKET=1` - Set when the Upgrade header contains "websocket"
   - `IS_UPGRADE=1` - Set when the Connection header contains "upgrade"

3. **RequestHeader set**:
   - `RequestHeader set Upgrade "websocket" env=IS_WEBSOCKET` - Re-adds the Upgrade header only when IS_WEBSOCKET is set
   - `RequestHeader set Connection "Upgrade" env=IS_UPGRADE` - Re-adds the Connection header only when IS_UPGRADE is set

### Why This Approach?

- **Simple and Reliable**: No complex RewriteRules or timing issues
- **Selective Application**: Only applies to WebSocket requests (when the environment variables are set)
- **Flask Compatibility**: Flask's gevent-websocket can now detect the Upgrade header and handle the WebSocket upgrade
- **Maintains Routing Logic**: Flask can still inspect Referer, session, and other headers to determine container routing
- **Works Across Apache Versions**: Compatible with Apache 2.4+ which most modern systems use

### Alternative Approach (If SetEnvIf Doesn't Work)

If your Apache version has issues with `SetEnvIf`, you can use RewriteRules with environment variables:

```apache
RewriteEngine On
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteCond %{HTTP:Connection} upgrade [NC]
RewriteRule ^/(.*) http://localhost:5020/$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]
RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE
RequestHeader set Connection %{CONNECTION}e env=CONNECTION

# General proxy for all non-WebSocket HTTP routes
ProxyPass / http://localhost:5020/ retry=3 timeout=3600
ProxyPassReverse / http://localhost:5020/
```

**Note**: The RewriteRule approach can have timing issues where the environment variables aren't set before the headers are processed, which is why the SetEnvIf approach is recommended.

## Testing

### 1. Verify Apache Syntax

```bash
sudo apache2ctl configtest
```

Should return: `Syntax OK`

### 2. Reload Apache

```bash
sudo systemctl reload apache2
```

### 3. Test WebSocket Connection

1. Start a desktop container
2. Access the container page: `https://your-domain.com/desktop/username-desktoptype`
3. Open browser DevTools → Console
4. Check for WebSocket connection in Network tab
5. Should see status `101 Switching Protocols` (not `1006 Connection closed`)

### 4. Check Flask Logs

```bash
docker-compose logs -f app | grep websockify
```

**Expected logs after fix**:
```
[INFO] WebSocket request at /websockify with Referer: https://domain/desktop/user-container
[INFO] WebSocket upgrade request detected
[INFO] wsgi.websocket object is available
[INFO] Found container from Referer: user-container
[INFO] Proxying WebSocket to container on port 7001
[INFO] Successfully connected to container port 7001
[INFO] WebSocket upgrade successful, starting bidirectional proxy
```

## Technical Details

### Why Hop-by-Hop Headers Are Stripped

HTTP/1.1 specification (RFC 7230, Section 6.1) defines hop-by-hop headers as headers that are meaningful only for a single transport-level connection and must not be forwarded by proxies. This is because:

1. **Connection Management**: These headers control the specific connection between two endpoints
2. **Protocol Upgrades**: Upgrade headers signal a protocol change for the current connection
3. **Proxy Independence**: Each hop in a proxy chain should manage its own connection parameters

### Why WebSocket Requires Special Handling

WebSocket is unique because it:
1. Starts as an HTTP request with `Upgrade: websocket` header
2. Upgrades to a persistent bidirectional connection
3. Requires the proxy to forward the upgrade request to the backend
4. The backend (Flask with gevent-websocket) needs to see the upgrade headers to perform the handshake

Without forwarding these headers:
- Flask sees a regular HTTP request without `Upgrade` header
- gevent-websocket doesn't detect it as a WebSocket upgrade request
- Flask returns a regular HTTP response instead of upgrading
- The browser's WebSocket connection fails

## Alternative Approaches Considered

### 1. Using ProxyPass with upgrade=websocket

```apache
ProxyPass / http://localhost:5020/ upgrade=websocket
```

**Why not used**: This makes Apache handle the WebSocket upgrade itself, which prevents Flask from:
- Inspecting the Referer header to determine container routing
- Accessing session data for container lookup
- Performing authentication checks before upgrading

### 2. Using mod_proxy_wstunnel directly

```apache
ProxyPass /websockify ws://localhost:5020/websockify
```

**Why not used**: Similar issue - Apache establishes a WebSocket connection to Flask, but Flask needs to receive the HTTP upgrade request with all headers intact for routing logic.

### 3. Using nginx instead of Apache

nginx has built-in support for WebSocket proxying that preserves headers better. However:
- The deployment already uses Apache
- This fix resolves the issue without requiring infrastructure changes
- Apache with this configuration works correctly

## Files Modified

1. **apache.conf**: Added environment variables and RequestHeader directives to preserve WebSocket headers

## Related Issues

- Original issue: WebSocket connections failing with code 1006
- Flask logs showing "NOT a WebSocket upgrade request"
- NoVNC unable to establish VNC connection

## Success Criteria

✅ Flask receives WebSocket upgrade requests with `Upgrade` and `Connection` headers
✅ Flask logs show "WebSocket upgrade request detected"
✅ Browser WebSocket connection shows status 101 (Switching Protocols)
✅ NoVNC successfully connects to containers
✅ No more code 1006 connection failures

## References

- [Apache mod_proxy_wstunnel Documentation](https://httpd.apache.org/docs/2.4/mod/mod_proxy_wstunnel.html)
- [Apache mod_headers Documentation](https://httpd.apache.org/docs/2.4/mod/mod_headers.html)
- [RFC 6455 - The WebSocket Protocol](https://tools.ietf.org/html/rfc6455)
- [RFC 7230 - HTTP/1.1 Message Syntax and Routing (Hop-by-hop headers)](https://tools.ietf.org/html/rfc7230#section-6.1)
