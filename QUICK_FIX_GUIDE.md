# Quick Fix Verification Guide

## What Was Fixed

The WebSocket connection issue where Apache was not forwarding WebSocket upgrade requests to Flask has been fixed.

**Problem**: Flask's WebSocket handlers were never being called because Apache was handling the WebSocket upgrade itself.

**Solution**: Changed Apache configuration to forward HTTP upgrade requests to Flask instead of establishing WebSocket connections.

## How to Apply the Fix

### 1. Update Your Apache Configuration

Edit your Apache site configuration (usually `/etc/apache2/sites-available/iserv-remote-desktop.conf`):

```bash
sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf
```

Find these lines:
```apache
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteRule /(.*) ws://localhost:5020/$1 [P,L]

ProxyPass / http://localhost:5020/ retry=3 timeout=3600 upgrade=websocket
```

Change them to:
```apache
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteRule /(.*) http://localhost:5020/$1 [P,L]

ProxyPass / http://localhost:5020/ retry=3 timeout=3600
```

**Key changes**:
- `ws://` → `http://` in RewriteRule
- Remove `upgrade=websocket` from ProxyPass

### 2. Test Apache Configuration

```bash
sudo apache2ctl configtest
```

Should output: `Syntax OK`

### 3. Reload Apache

```bash
sudo systemctl reload apache2
```

### 4. Verify Flask Receives Requests

Watch Flask logs in real-time:
```bash
docker-compose logs -f app | grep -i websocket
```

### 5. Test WebSocket Connection

1. Open your application in a browser
2. Start a desktop container
3. Wait 10-15 seconds for container to be ready
4. Access the desktop

**Expected Flask logs**:
```
[INFO] WebSocket request at /websockify with Referer: https://your-domain/desktop/username-container
[INFO] WebSocket upgrade request detected
[INFO] wsgi.websocket object is available
[DEBUG] Found container from Referer: username-container
[INFO] Proxying WebSocket to container container_name on port 7XXX
[INFO] Successfully connected to container port 7XXX
[INFO] WebSocket upgrade successful, starting bidirectional proxy
```

**Browser DevTools (Network → WS tab)**:
- Status: `101 Switching Protocols` ✓
- Connection stays open (green indicator) ✓
- No code 1005 error ✓

## Troubleshooting

### Still Getting Code 1005?

**Check 1**: Verify Apache config is correct
```bash
sudo grep -A 1 "RewriteRule" /etc/apache2/sites-available/iserv-remote-desktop.conf | grep websocket
```
Should show: `RewriteRule /(.*) http://localhost:5020/$1 [P,L]`

**Check 2**: Verify Flask is receiving requests
```bash
# Restart logging with debug level
docker-compose logs -f app 2>&1 | grep -i "websocket\|upgrade"
```
If you see no logs, Apache is not forwarding to Flask.

**Check 3**: Verify Apache modules
```bash
apache2ctl -M | grep proxy
```
Should show:
- `proxy_module (shared)`
- `proxy_http_module (shared)`
- `proxy_wstunnel_module (shared)`

**Check 4**: Check Apache error logs
```bash
sudo tail -50 /var/log/apache2/iserv-remote-desktop-error.log
```

### Flask Logs Show "wsgi.websocket object is NOT available"

This means Flask is receiving the request but gevent-websocket is not handling it.

**Solution**: Verify gunicorn worker class
```bash
docker-compose exec app ps aux | grep gunicorn
```

Should include: `--worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker`

If not:
```bash
docker-compose down
docker-compose up -d --build
```

### Container Connection Still Fails

If Flask is receiving WebSocket requests but connection to container fails:

**Check 1**: Container is running
```bash
docker ps | grep <username>
```

**Check 2**: Container port is accessible
```bash
# Replace 7XXX with actual container port from Flask logs
curl -k https://localhost:7XXX/
```

**Check 3**: Wait longer for container startup
Kasm containers can take 15-20 seconds to fully start.

## Success Indicators

✓ Apache forwards HTTP request with Upgrade header to Flask
✓ Flask logs show "WebSocket request at /websockify"
✓ Flask logs show "wsgi.websocket object is available"
✓ Flask logs show "Successfully connected to container port"
✓ Browser shows WebSocket status 101 Switching Protocols
✓ Browser WebSocket connection stays open
✓ noVNC display shows desktop

## Why This Fix Works

**Before**:
1. Browser → Apache: WebSocket upgrade request
2. Apache handles upgrade itself (because of `ws://` in RewriteRule)
3. Apache tries to establish WebSocket to Flask
4. Flask never receives HTTP headers (Referer, session)
5. Flask can't determine which container to route to
6. Connection fails

**After**:
1. Browser → Apache: WebSocket upgrade request
2. Apache forwards as HTTP request with Upgrade header
3. Flask receives HTTP request, inspects headers
4. Flask determines correct container from Referer/session
5. gevent-websocket upgrades the connection
6. Flask proxies to correct container
7. WebSocket connection established successfully

## Related Documentation

- [WEBSOCKET_APACHE_FIX.md](WEBSOCKET_APACHE_FIX.md) - Complete technical explanation
- [APACHE_SETUP.md](APACHE_SETUP.md) - Full Apache setup guide
- [WEBSOCKET_CONNECTION_FIX.md](WEBSOCKET_CONNECTION_FIX.md) - WebSocket error handling

## Need Help?

If you're still experiencing issues after applying this fix:

1. Collect logs:
   ```bash
   # Apache logs
   sudo tail -100 /var/log/apache2/iserv-remote-desktop-error.log > apache-logs.txt
   
   # Flask logs
   docker-compose logs --tail=200 app > flask-logs.txt
   
   # Apache config
   sudo cat /etc/apache2/sites-available/iserv-remote-desktop.conf > apache-config.txt
   ```

2. Check that Flask debug points are being triggered:
   - Search flask-logs.txt for "WebSocket request at /websockify"
   - If not found, Apache is not forwarding requests to Flask

3. Verify the fix is applied:
   - Search apache-config.txt for "RewriteRule"
   - Should show `http://localhost:5020/` not `ws://localhost:5020/`
   - ProxyPass should NOT have `upgrade=websocket`
