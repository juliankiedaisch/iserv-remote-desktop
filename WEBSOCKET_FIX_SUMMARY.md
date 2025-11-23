# WebSocket Code 1005 Fix - Summary

## Issue Fixed
**Problem**: WebSocket connections successfully upgraded (HTTP 101) but immediately closed with code 1005 ("no status received"), preventing noVNC from connecting to Kasm containers.

**Error Message**:
```
GET wss://desktop.hub.mdg-hamburg.de/websockify [HTTP/1.1 101 Switching Protocols 14ms]
Failed when connecting: Connection closed (code: 1005)
```

## Root Cause
The WebSocket proxy tried to return HTTP Response objects after the WebSocket was already established, causing connections to close without proper WebSocket close frames.

## Solution Summary

### Key Changes
1. ✅ **Fixed WebSocket Error Handling**: Removed HTTP Response returns after WebSocket establishment
2. ✅ **Added Proper Close Frames**: Using `ws.close(code, reason)` with appropriate status codes
3. ✅ **Added Timeouts**: 10-second timeout for container connections
4. ✅ **Enhanced Logging**: Comprehensive INFO/DEBUG/ERROR logging with tracebacks
5. ✅ **Simplified Apache Config**: Removed conflicting WebSocket handling rules
6. ✅ **Security**: CodeQL scan passed with 0 alerts

### WebSocket Close Codes
| Code | Meaning | When Used |
|------|---------|-----------|
| 1002 | Protocol Error | Container rejected WebSocket connection |
| 1009 | Message Too Big | Handshake response exceeded 8KB |
| 1011 | Internal Error | Cannot connect to container or server error |

## Architecture Understanding

### Physical Deployment
```
Server 1 (Web)              Server 2 (Docker)
┌─────────────┐            ┌──────────────────┐
│   Apache    │────────────│  Container 7001  │
│ Let's       │   Network  │  Container 7002  │
│ Encrypt     │            │  Container 7005  │
│   Cert      │            │  Self-Signed     │
└──────┬──────┘            │  Certificates    │
       │                   └──────────────────┘
       │
┌──────▼──────┐
│    Flask    │
│  Database   │
│  (Routing)  │
└─────────────┘
```

### SSL Certificate Chain
1. **Public**: Browser → Apache (Let's Encrypt wildcard - TRUSTED)
2. **Internal**: Apache → Flask (unencrypted localhost ws://)
3. **Container**: Flask → Docker Host (self-signed cert - UNTRUSTED, verify disabled)

### Why Flask is Essential
1. **Physical Separation**: Apache on different server than containers
2. **Multi-User Routing**: Multiple users, multiple containers, simultaneous access
3. **Dynamic Ports**: Database lookup needed (username + desktop → port)
4. **SSL Handling**: Must disable verification for self-signed container certs

## Files Modified

| File | Changes |
|------|---------|
| `app/routes/proxy_routes.py` | Fixed WebSocket error handling, added close frames, enhanced logging, comprehensive documentation |
| `apache.conf` | Simplified WebSocket configuration, removed conflicts |
| `WEBSOCKET_CONNECTION_FIX.md` | Comprehensive guide with diagrams and troubleshooting |
| `APACHE_SETUP.md` | Added WebSocket code 1005 troubleshooting section |
| `WEBSOCKET_FIX_SUMMARY.md` | This summary document |

## Testing Checklist

### Application Logs
```bash
docker-compose logs -f app | grep websockify
```

Expected log sequence:
```
[INFO] WebSocket request at /websockify with Referer: ...
[INFO] WebSocket upgrade request detected
[INFO] wsgi.websocket object is available
[INFO] Attempting to connect to container at localhost:XXXX
[INFO] Successfully connected to container port XXXX
[INFO] WebSocket upgrade successful, starting bidirectional proxy
```

### Browser Testing
1. ✓ Start container, wait 10-15 seconds
2. ✓ Access desktop page
3. ✓ Open DevTools → Network → WS
4. ✓ Check `/websockify`: Status 101, stays open
5. ✓ No code 1005 errors
6. ✓ noVNC display loads

### Common Issues

#### "Failed to connect to container port"
- **Cause**: Container not running or VNC server not started yet
- **Solution**: Wait 10-15 seconds, check `docker ps`, check container logs

#### "Container did not accept WebSocket upgrade"
- **Cause**: VNC authentication failed or wrong certificate handling
- **Solution**: Verify `VNC_PASSWORD`, ensure `KASM_VERIFY_SSL=false`

#### "wsgi.websocket object is NOT available"
- **Cause**: Flask not running with gevent-websocket worker
- **Solution**: Check `entrypoint.sh` has `GeventWebSocketWorker`, restart app

## Deployment Steps

1. **Pull latest changes**:
   ```bash
   git pull origin copilot/fix-websocket-connection
   ```

2. **Restart application**:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

3. **Monitor logs**:
   ```bash
   docker-compose logs -f app
   ```

4. **Test with user**:
   - Log in as test user
   - Start a container
   - Wait 15 seconds
   - Access desktop
   - Verify noVNC connection works

## Success Criteria

- [x] Code changes committed and pushed
- [x] Code review feedback addressed
- [x] Security scan passed (0 alerts)
- [x] Documentation complete
- [ ] Deployed to test environment
- [ ] Tested with actual containers
- [ ] noVNC displays work correctly
- [ ] No code 1005 errors in browser console

## Support

If issues persist after applying this fix:

1. **Check Apache WebSocket support**:
   ```bash
   apache2ctl -M | grep proxy_wstunnel
   ```

2. **Check gevent-websocket installed**:
   ```bash
   docker-compose exec app pip list | grep gevent
   ```

3. **Check database for container ports**:
   ```bash
   docker-compose exec app python3 -c "
   from app import create_app, db
   from app.models.containers import Container
   app = create_app(False)
   with app.app_context():
       for c in Container.query.all():
           print(f'{c.username}-{c.desktop_type}: port {c.host_port}')
   "
   ```

4. **Test container WebSocket directly**:
   ```bash
   wscat -c wss://localhost:<port>/websockify --no-check
   ```

## Related Documentation

- [WEBSOCKET_CONNECTION_FIX.md](WEBSOCKET_CONNECTION_FIX.md) - Detailed technical guide
- [WEBSOCKET_FIX.md](WEBSOCKET_FIX.md) - Original WebSocket implementation
- [PROXY_FIXES.md](PROXY_FIXES.md) - Proxy routing fixes
- [APACHE_SETUP.md](APACHE_SETUP.md) - Apache configuration guide

---

**Date**: 2025-11-23  
**Issue**: WebSocket connection code 1005  
**Status**: ✅ Fixed and ready for testing  
**Security**: ✅ CodeQL scan passed (0 alerts)
