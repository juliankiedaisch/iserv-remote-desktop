# Proxy Routing Fixes - Testing Guide

## Overview
This document provides guidance for testing the proxy routing fixes in a live environment.

## Test Scenarios

### 1. Nested Asset References (Fonts, Images)

**What was broken:**
- Font files referenced in CSS returned 404 errors
- Example: `/desktop/assets/Orbitron700-DI3tXiXq.woff` failed when loaded by CSS

**How to test:**
1. Start a container (e.g., ubuntu-vscode)
2. Access the desktop page: `/desktop/<username>-<desktop-type>`
3. Verify the page loads completely with all fonts rendering correctly
4. Check browser DevTools Network tab - no 404 errors for font files
5. Check browser console - no errors about missing font resources

**Expected result:** All fonts load successfully, no 404 errors

### 2. App Path (Locale Files)

**What was broken:**
- Locale files at `/desktop/app/locale/de.json` returned 404 errors

**How to test:**
1. Start a container
2. Access the desktop page
3. Try to change the language/locale if the UI supports it
4. Check browser DevTools Network tab for `/desktop/app/locale/*.json` requests
5. Verify locale files load with 200 status

**Expected result:** Locale files load successfully, language changes work

### 3. WebSocket Connections

**What was broken:**
- WebSocket connections at `/websockify` failed with 400 errors
- VNC connection failed to establish

**How to test:**
1. Start a container
2. Access the desktop page
3. Wait for the VNC/desktop interface to load
4. Verify you can see and interact with the desktop
5. Check browser DevTools Network tab - WebSocket connection should show "101 Switching Protocols"
6. Check for `/websockify` requests - should not have 400 errors

**Expected result:** Desktop interface loads and is interactive, WebSocket connects successfully

### 4. Session Persistence

**What's new:**
- Container selection is stored in session
- Multiple tabs/windows should maintain connection to the same container

**How to test:**
1. Start a container and access the desktop page
2. Open a new tab and navigate to an asset directly: `/desktop/assets/ui.css`
3. The asset should load (using session fallback)
4. Try opening the desktop page in multiple tabs
5. All tabs should maintain their connection

**Expected result:** Assets load correctly across tabs, session is maintained

## Debugging

If issues occur, check the Flask application logs for:

```
DEBUG in proxy_routes: Stored container in session: <container-name>
DEBUG in proxy_routes: Trying container from session: <container-name>
DEBUG in proxy_routes: Found container from session: <container-name>
```

These log messages indicate the session fallback is working correctly.

## Common Issues

### Issue: Assets still return 404
**Possible cause:** Session not configured properly
**Solution:** Ensure Flask session is configured with a SECRET_KEY

### Issue: WebSocket still returns 400
**Possible cause:** Session cookie not being sent
**Solution:** Check browser cookie settings, ensure cookies are enabled

### Issue: Different tabs show different containers
**Possible cause:** Session isolation
**Solution:** This is expected - each browser/session tracks its own container

## Performance Notes

- Session storage is minimal (only container name)
- No database queries for session lookups
- Session cleanup happens automatically via Flask's session management
- No impact on container performance

## Rollback Plan

If issues occur in production:
1. The changes are backward compatible
2. Revert to previous commit: `git revert HEAD`
3. The old Referer-only logic will still work for direct asset loads
4. Only nested assets and WebSocket will fail (existing issues)

## Success Criteria

✅ Desktop pages load completely with all assets
✅ Fonts render correctly (no missing glyphs)
✅ Locale/language switching works
✅ WebSocket connections establish successfully
✅ Desktop interface is fully interactive
✅ No 404 errors in browser console
✅ No 400 errors for WebSocket connections
