# WebSocket Fix - Quick Reference

## Problem
WebSocket connections fail with error code 1006. Flask logs show "NOT a WebSocket upgrade request".

## Cause
Apache strips `Upgrade` and `Connection` headers when proxying requests.

## Solution (Recommended)
Add these directives to your Apache configuration using `SetEnvIf`:

```apache
# Detect WebSocket upgrade requests and set an environment variable
SetEnvIf Upgrade "(?i)websocket" IS_WEBSOCKET=1
SetEnvIf Connection "(?i)upgrade" IS_UPGRADE=1

# Preserve WebSocket headers for requests that have them
RequestHeader set Upgrade "websocket" env=IS_WEBSOCKET
RequestHeader set Connection "Upgrade" env=IS_UPGRADE
```

### Alternative (If SetEnvIf doesn't work)
Use RewriteRules instead:

```apache
RewriteEngine On
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteCond %{HTTP:Connection} upgrade [NC]
RewriteRule ^/(.*) http://localhost:5020/$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]
RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE
RequestHeader set Connection %{CONNECTION}e env=CONNECTION
```

## Quick Deploy

1. Edit Apache config: `sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf`
2. Add the SetEnvIf directives above (place BEFORE ProxyPass)
3. Test: `sudo apache2ctl configtest`
4. Reload: `sudo systemctl reload apache2`
5. Verify: `docker-compose logs -f app | grep "WebSocket upgrade request detected"`

## Testing

Run the test script:
```bash
./scripts/test_apache_websocket_headers.sh localhost:5020 http
# Or for production:
./scripts/test_apache_websocket_headers.sh your-domain.com https
```

## Expected Result
- ✅ Flask logs: "WebSocket upgrade request detected"
- ✅ Browser: Status 101 Switching Protocols
- ✅ Desktop loads successfully

## Detailed Documentation
- [WEBSOCKET_HEADER_FIX.md](WEBSOCKET_HEADER_FIX.md) - Complete technical explanation with both approaches
- [TESTING_WEBSOCKET_FIX.md](TESTING_WEBSOCKET_FIX.md) - Testing procedures
- [APACHE_SETUP.md](APACHE_SETUP.md) - Full Apache setup guide
- [apache.conf](apache.conf) - Reference configuration with SetEnvIf approach

