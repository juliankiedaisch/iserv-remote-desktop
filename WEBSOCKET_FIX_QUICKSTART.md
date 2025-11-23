# WebSocket Fix - Quick Reference

## Problem
WebSocket connections fail with error code 1006. Flask logs show "NOT a WebSocket upgrade request".

## Cause
Apache strips `Upgrade` and `Connection` headers when proxying requests.

## Solution
Add these directives to your Apache configuration:

```apache
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteCond %{HTTP:Connection} upgrade [NC]
RewriteRule ^/(.*) http://localhost:5020/$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]
RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE
RequestHeader set Connection %{CONNECTION}e env=CONNECTION
```

## Quick Deploy

1. Edit Apache config: `sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf`
2. Add the directives above (adjust port if needed)
3. Test: `sudo apache2ctl configtest`
4. Reload: `sudo systemctl reload apache2`
5. Verify: `docker-compose logs -f app | grep "WebSocket upgrade request detected"`

## Expected Result
- ✅ Flask logs: "WebSocket upgrade request detected"
- ✅ Browser: Status 101 Switching Protocols
- ✅ Desktop loads successfully

## Detailed Documentation
- [WEBSOCKET_HEADER_FIX.md](WEBSOCKET_HEADER_FIX.md) - Complete technical explanation
- [TESTING_WEBSOCKET_FIX.md](TESTING_WEBSOCKET_FIX.md) - Testing procedures
- [APACHE_SETUP.md](APACHE_SETUP.md) - Full Apache setup guide

## Validation
Run: `./scripts/validate_apache_websocket.sh`

This script checks:
- Required Apache modules
- Configuration syntax
- WebSocket header forwarding directives
