# Testing WebSocket Header Forwarding Fix

This guide explains how to test that the WebSocket header forwarding fix is working correctly.

## Prerequisites

- Apache is installed and configured
- The Flask application is running (via docker-compose or directly)
- You have access to the server where Apache is running

## Quick Validation

Run the validation script:

```bash
./scripts/validate_apache_websocket.sh
```

This script will check:
- Required Apache modules are enabled
- Apache configuration syntax is valid
- WebSocket header forwarding directives are present

## Step-by-Step Testing

### 1. Verify Apache Configuration

Check that your Apache configuration includes the WebSocket header forwarding directives:

```bash
# Find your Apache configuration file
sudo grep -r "E=UPGRADE" /etc/apache2/sites-enabled/
```

You should see:
```apache
RewriteRule ^/(.*) http://localhost:5020/$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]
RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE
RequestHeader set Connection %{CONNECTION}e env=CONNECTION
```

### 2. Reload Apache

After updating the configuration:

```bash
# Test configuration syntax
sudo apache2ctl configtest

# If OK, reload Apache
sudo systemctl reload apache2
```

### 3. Start the Flask Application

```bash
# If using docker-compose
docker-compose up -d

# If running directly
python3 run.py
```

Verify the application is running:
```bash
curl http://localhost:5020/health
```

### 4. Test WebSocket Connection

#### Method 1: Through the Browser

1. Log in to the application
2. Start a desktop container (wait 10-15 seconds for it to start)
3. Access the desktop page
4. Open browser DevTools (F12)
5. Go to the **Network** tab
6. Filter by "WS" (WebSocket)
7. Look for a connection to `/websockify`

**Expected results:**
- Status: `101 Switching Protocols` (not 1006 or 1005)
- Connection stays open (shows as "pending" with a green indicator)

**If it fails:**
- Status code 1006 or 1005 = headers not being forwarded
- Check Apache logs and Flask logs

#### Method 2: Check Flask Logs

Monitor Flask logs while accessing a desktop:

```bash
docker-compose logs -f app | grep -i websocket
```

**Expected log output BEFORE the fix:**
```
[INFO] WebSocket request at /websockify with Referer: https://domain/desktop/user-container
[INFO] NOT a WebSocket upgrade request  ← BAD: Headers not forwarded
```

**Expected log output AFTER the fix:**
```
[INFO] WebSocket request at /websockify with Referer: https://domain/desktop/user-container
[INFO] WebSocket upgrade request detected  ← GOOD: Headers forwarded!
[INFO] wsgi.websocket object is available
[INFO] Found container from Referer: user-container
[INFO] Proxying WebSocket to container container_name on port 7001
[INFO] Attempting to connect to container at localhost:7001
[INFO] Successfully connected to container port 7001
[INFO] WebSocket upgrade successful, starting bidirectional proxy
```

### 5. Verify Desktop Connection

After the WebSocket connection is established:

1. You should see the desktop loading screen
2. After a few seconds, the actual desktop environment should appear
3. Test keyboard and mouse input to verify bidirectional communication

**If the desktop doesn't load:**
- Check if the container is actually running: `docker ps | grep kasm`
- Check container logs: `docker logs <container_name>`
- Verify VNC password is set correctly in `.env`

## Troubleshooting

### Issue: Flask logs still show "NOT a WebSocket upgrade request"

**Diagnosis:** Headers are not being forwarded by Apache

**Solutions:**
1. Verify the RewriteRule includes environment variables:
   ```bash
   sudo grep "E=UPGRADE" /etc/apache2/sites-enabled/*.conf
   ```

2. Verify RequestHeader directives are present:
   ```bash
   sudo grep "RequestHeader set Upgrade" /etc/apache2/sites-enabled/*.conf
   sudo grep "RequestHeader set Connection" /etc/apache2/sites-enabled/*.conf
   ```

3. Ensure `mod_headers` is enabled:
   ```bash
   sudo a2enmod headers
   sudo systemctl restart apache2
   ```

4. Check that the RequestHeader directives are AFTER the RewriteRule in the configuration

### Issue: Browser shows "Connection closed (code: 1006)"

**Diagnosis:** Multiple possible causes

**Solutions:**
1. Check Flask logs for the actual error
2. Verify container is running: `docker ps | grep kasm`
3. Test container WebSocket endpoint directly:
   ```bash
   # Install wscat if not available
   npm install -g wscat
   
   # Test container connection (replace 7001 with your container port)
   wscat -c wss://localhost:7001/websockify --no-check
   ```
4. Verify VNC credentials are correct in `.env`

### Issue: Apache fails to start after configuration change

**Diagnosis:** Syntax error in configuration

**Solutions:**
1. Check syntax:
   ```bash
   sudo apache2ctl configtest
   ```

2. Common syntax errors:
   - Missing closing quote in environment variable
   - Typo in module name (should be `UPGRADE` not `Upgrade`)
   - Missing `env=UPGRADE` condition in RequestHeader

3. Verify the exact syntax from `apache.conf`:
   ```apache
   RewriteRule ^/(.*) http://localhost:5020/$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]
   RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE
   RequestHeader set Connection %{CONNECTION}e env=CONNECTION
   ```

### Issue: Headers are forwarded but WebSocket still fails

**Diagnosis:** Issue with Flask or container

**Solutions:**
1. Verify Flask is using gevent-websocket:
   ```bash
   docker-compose exec app ps aux | grep gunicorn
   # Should show: --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker
   ```

2. Check if container accepts WebSocket connections:
   ```bash
   docker exec -it <container_name> netstat -tlnp | grep 6901
   ```

3. Verify SSL settings in `.env`:
   ```bash
   KASM_CONTAINER_PROTOCOL=https
   KASM_VERIFY_SSL=false
   ```

## Automated Testing

### Unit Test (Development)

Run the test suite:

```bash
python3 -m pytest tests/ -v
```

Look for WebSocket-related tests:
```bash
python3 -m pytest tests/test_websocket_proxy_fix.py -v
python3 -m pytest tests/test_websocket_routing.py -v
```

### Integration Test (Production-like)

1. Start all services:
   ```bash
   docker-compose up -d
   ```

2. Run integration tests:
   ```bash
   python3 tests/test_proxy_integration.py
   ```

### Manual Verification Checklist

- [ ] Apache configuration syntax is valid (`apache2ctl configtest`)
- [ ] Required modules are enabled (`apache2ctl -M`)
- [ ] WebSocket headers are in configuration (`grep "E=UPGRADE"`)
- [ ] RequestHeader directives are present (`grep "RequestHeader set Upgrade"`)
- [ ] Apache has been reloaded (`systemctl reload apache2`)
- [ ] Flask application is running (`curl localhost:5020/health`)
- [ ] Flask logs show "WebSocket upgrade request detected"
- [ ] Browser DevTools shows 101 Switching Protocols
- [ ] Desktop loads and is interactive
- [ ] No errors in browser console
- [ ] No errors in Apache logs
- [ ] No errors in Flask logs

## Success Criteria

✅ Flask logs show: "WebSocket upgrade request detected"
✅ Browser WebSocket shows: Status 101 Switching Protocols
✅ Desktop loads within 5-10 seconds
✅ Keyboard and mouse input work correctly
✅ No connection drops or reconnections
✅ No code 1006 or 1005 errors

## Performance Validation

After confirming WebSocket works, test performance:

1. **Connection Latency**: 
   - WebSocket should establish within 1-2 seconds
   - Desktop should load within 10-15 seconds

2. **Input Responsiveness**:
   - Keyboard input should have minimal delay (<100ms)
   - Mouse movement should be smooth

3. **Stability**:
   - Connection should remain stable for extended periods (hours)
   - No unexpected disconnections

## Rollback Procedure

If the fix causes issues, rollback:

1. Restore previous Apache configuration:
   ```bash
   sudo cp /etc/apache2/sites-available/iserv-remote-desktop.conf.bak \
          /etc/apache2/sites-available/iserv-remote-desktop.conf
   sudo systemctl reload apache2
   ```

2. Restart services:
   ```bash
   docker-compose restart
   ```

3. Verify services are running:
   ```bash
   docker-compose ps
   ```

## Documentation

For more information, see:
- [WEBSOCKET_HEADER_FIX.md](../WEBSOCKET_HEADER_FIX.md) - Detailed explanation of the fix
- [APACHE_SETUP.md](../APACHE_SETUP.md) - Complete Apache setup guide
- [WEBSOCKET_FIX.md](../WEBSOCKET_FIX.md) - Original WebSocket implementation

## Support

If you encounter issues:
1. Check all logs (Apache + Flask + Container)
2. Verify all prerequisites are met
3. Review the troubleshooting section above
4. Open an issue with:
   - Apache configuration (sanitized)
   - Flask logs
   - Browser console errors
   - Network tab screenshots
