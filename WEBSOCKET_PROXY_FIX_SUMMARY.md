# WebSocket Proxy Fix Summary

## Issue Description

Users reported WebSocket connection failures when using Apache as a reverse proxy with the following symptoms:

**Log Output:**
```
[2025-11-23 13:29:37,036] INFO in proxy_routes: WebSocket request at /websockify with Referer:
[2025-11-23 13:29:37,036] DEBUG in proxy_routes: Session has current_container: True
[2025-11-23 13:29:37,036] INFO in proxy_routes: NOT a WebSocket upgrade request
[2025-11-23 13:29:37,036] WARNING in proxy_routes: No Referer header in WebSocket request
[2025-11-23 13:29:37,061] INFO in proxy_routes: Proxying WebSocket to container...
[2025-11-23 13:29:37,061] DEBUG in proxy_routes: Regular HTTP request to /websockify (not WebSocket)
```

**Problem:** Apache was not forwarding the `Upgrade` and `Connection` headers to Flask, causing Flask to treat WebSocket upgrade requests as regular HTTP requests.

## Root Cause

When Apache's `mod_proxy` forwards requests, it strips "hop-by-hop" headers by default, including:
- `Upgrade`
- `Connection`
- `Keep-Alive`
- `Transfer-Encoding`

These headers are normally stripped because they apply to the connection between the client and proxy, not between proxy and backend. However, for WebSocket upgrades to work with Flask's gevent-websocket, these headers **must** be forwarded.

The previous Apache configuration attempted to preserve headers using environment variables set by RewriteRule, but this approach had timing issues where headers weren't properly set before the proxy decision was made.

## Solution

### Primary Fix: SetEnvIf Approach (Recommended)

The most reliable solution uses Apache's `SetEnvIf` directive to detect WebSocket requests and conditionally preserve headers:

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

**How it works:**
1. `SetEnvIf` checks incoming requests for WebSocket headers (case-insensitive)
2. Environment variables (`IS_WEBSOCKET`, `IS_UPGRADE`) are set when headers are detected
3. `RequestHeader set` adds headers back to proxied request only when env vars are set
4. Flask receives the headers and can detect WebSocket upgrades

**Advantages:**
- Simple and reliable
- No RewriteRules needed
- Works across Apache 2.4+ versions
- No timing issues

### Alternative Fix: RewriteRule Approach

If `SetEnvIf` doesn't work on your Apache version, use RewriteRules:

```apache
RewriteEngine On
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteCond %{HTTP:Connection} upgrade [NC]
RewriteRule ^/(.*) http://localhost:5020/$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]
RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE
RequestHeader set Connection %{CONNECTION}e env=CONNECTION
```

**Note:** This approach can have timing issues in some Apache configurations where environment variables aren't set before headers are processed.

## Implementation Steps

### 1. Update Apache Configuration

Edit your Apache virtual host file:
```bash
sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf
```

Add the SetEnvIf directives BEFORE the `ProxyPass` directive.

### 2. Enable Required Modules

Ensure the headers module is enabled:
```bash
sudo a2enmod headers
```

### 3. Test Configuration

```bash
sudo apache2ctl configtest
```

Should return: `Syntax OK`

### 4. Reload Apache

```bash
sudo systemctl reload apache2
```

### 5. Verify the Fix

Check Flask logs:
```bash
docker-compose logs -f app | grep websockify
```

You should now see:
```
[INFO] WebSocket request at /websockify
[INFO] WebSocket upgrade request detected
[INFO] wsgi.websocket object is available
[INFO] Proxying WebSocket to container on port XXXX
```

### 6. Test with Script

Run the provided test script:
```bash
./scripts/test_apache_websocket_headers.sh localhost:5020 http
```

Or for production:
```bash
./scripts/test_apache_websocket_headers.sh your-domain.com https
```

## Files Modified

1. **apache.conf** - Updated with SetEnvIf approach (recommended configuration)
2. **WEBSOCKET_HEADER_FIX.md** - Documented both approaches with technical details
3. **APACHE_SETUP.md** - Added improved troubleshooting section
4. **WEBSOCKET_FIX_QUICKSTART.md** - Quick reference with both approaches
5. **scripts/test_apache_websocket_headers.sh** - New test script to verify configuration

## Testing

### Automated Testing

Use the test script:
```bash
./scripts/test_apache_websocket_headers.sh [domain] [protocol] [health-endpoint]
```

Example:
```bash
# Local testing
./scripts/test_apache_websocket_headers.sh localhost:5020 http

# Production testing
./scripts/test_apache_websocket_headers.sh your-domain.com https /
```

### Manual Testing

1. Start a desktop container
2. Access the desktop page in browser
3. Open browser DevTools → Network tab
4. Look for WebSocket connection to `/websockify`
5. Should show status `101 Switching Protocols`
6. Connection should stay open (not close immediately)

### Expected Results

**✅ Success Indicators:**
- Flask logs show "WebSocket upgrade request detected"
- Browser shows HTTP 101 status for WebSocket
- Desktop loads and displays correctly
- No code 1005 or 1006 connection errors

**❌ Failure Indicators:**
- Flask logs show "NOT a WebSocket upgrade request"
- Browser shows HTTP 200 or 404
- Desktop shows black screen or connection errors
- Code 1005/1006 errors in console

## Troubleshooting

### Still seeing "NOT a WebSocket upgrade request"

1. **Check module is enabled:**
   ```bash
   sudo a2enmod headers
   sudo systemctl reload apache2
   ```

2. **Verify directive placement:**
   - SetEnvIf/RequestHeader must be BEFORE ProxyPass
   - Check you're editing the correct virtual host

3. **Check for conflicting rules:**
   - Remove any `ProxyPass` with `ws://` protocol
   - Remove duplicate RewriteRules

4. **Restart Apache (not just reload):**
   ```bash
   sudo systemctl restart apache2
   ```

### Headers forwarded but connection still fails

1. **Container not running:**
   - Wait 10-15 seconds after starting
   - Check: `docker ps`

2. **Port not accessible:**
   - Check: `curl -k https://localhost:<port>/websockify`
   - Verify `KASM_CONTAINER_PROTOCOL=https` in `.env`

3. **SSL issues:**
   - Verify `KASM_VERIFY_SSL=false` in `.env`
   - Kasm containers use self-signed certificates

## Architecture

This fix maintains the existing architecture where:

1. **Browser** → Apache (wss:// with Let's Encrypt cert - TRUSTED)
2. **Apache** → Flask (ws:// or http:// localhost - UNENCRYPTED)
3. **Flask** → Container (wss:// with self-signed cert - UNTRUSTED, verify disabled)

Flask MUST be in the middle because:
- Multiple users with multiple containers simultaneously
- Dynamic port mapping (determined by database query)
- Physical server separation (Apache and containers on different machines)
- SSL certificate handling (self-signed certs on containers)
- Container routing logic (based on Referer, session, authentication)

## Benefits of This Fix

1. **Reliability:** SetEnvIf approach has no timing issues
2. **Simplicity:** No complex RewriteRules needed
3. **Compatibility:** Works across Apache 2.4+ versions
4. **Maintainability:** Clear and well-documented approach
5. **Testability:** Provided test script for verification
6. **Flexibility:** Alternative approach provided for edge cases

## References

- [Apache mod_headers Documentation](https://httpd.apache.org/docs/2.4/mod/mod_headers.html)
- [Apache mod_setenvif Documentation](https://httpd.apache.org/docs/2.4/mod/mod_setenvif.html)
- [RFC 6455 - The WebSocket Protocol](https://tools.ietf.org/html/rfc6455)
- [RFC 7230 - HTTP/1.1 Hop-by-hop Headers](https://tools.ietf.org/html/rfc7230#section-6.1)

## Related Documentation

- [WEBSOCKET_HEADER_FIX.md](WEBSOCKET_HEADER_FIX.md) - Complete technical explanation
- [APACHE_SETUP.md](APACHE_SETUP.md) - Full Apache setup guide
- [TESTING_WEBSOCKET_FIX.md](TESTING_WEBSOCKET_FIX.md) - Testing procedures
- [WEBSOCKET_FIX_QUICKSTART.md](WEBSOCKET_FIX_QUICKSTART.md) - Quick reference guide
