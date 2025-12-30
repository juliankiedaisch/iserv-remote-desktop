# Subdomain-Based Container Routing - Complete Guide

## 🎯 Solution Overview

Instead of path-based routing (`desktop.hub.mdg-hamburg.de/desktop/container-name`), use **subdomain-based routing** (`container-name.desktop.hub.mdg-hamburg.de`).

## ✅ Why Subdomains Solve the WebSocket Problem

| Issue | Path-Based | Subdomain-Based |
|-------|-----------|----------------|
| **Host header sent?** | ✅ Yes (but doesn't contain container) | ✅ Yes (contains container!) |
| **Referer header sent?** | ❌ No (security policy blocks it) | ✅ Not needed! |
| **Cookies required?** | ❌ Yes (but not sent by default) | ✅ Not needed! |
| **SSL certificate?** | ✅ Works | ✅ Works (wildcard) |
| **WebSocket config?** | ❌ Needs credentials: 'include' | ✅ Works out of the box! |

### The Key Insight

**The Host header is ALWAYS sent with every request**, including WebSocket upgrades! By encoding the container name in the subdomain, Flask can extract it reliably without depending on:
- Referer headers (blocked by browsers for security)
- Session cookies (not sent by noVNC by default)
- URL paths (require special WebSocket URL configuration)

## 📋 Implementation Checklist

### 1. DNS Configuration (Required First!)

Add a wildcard DNS record:

```
*.desktop.hub.mdg-hamburg.de  A  <your-server-ip>
```

**Example:**
```bash
# Test DNS resolution after configuring:
dig julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de
# Should return your server IP
```

### 2. Apache Configuration

The updated `apache.conf` now includes:

```apache
<VirtualHost *:443>
    ServerName desktop.hub.mdg-hamburg.de
    # Support wildcard subdomains for container-specific URLs
    ServerAlias *.desktop.hub.mdg-hamburg.de
    
    SSLEngine on
    # Your wildcard SSL certificate already covers *.desktop.hub.mdg-hamburg.de
    SSLCertificateFile /etc/ssl/certs/hub.combined
    SSLCertificateKeyFile /etc/ssl/private/hub.key
    
    # ... rest of config unchanged ...
</VirtualHost>

<VirtualHost *:80>
    ServerName desktop.hub.mdg-hamburg.de
    ServerAlias *.desktop.hub.mdg-hamburg.de
    
    # Redirect to HTTPS preserving subdomain
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
</VirtualHost>
```

**Deploy:**
```bash
# Copy to Apache
sudo cp apache.conf /etc/apache2/sites-available/desktop.conf

# Reload Apache
sudo systemctl reload apache2

# Test configuration
sudo apache2ctl configtest
```

### 3. Flask Application

The code in [app/routes/proxy_routes.py](/root/iserv-remote-desktop/app/routes/proxy_routes.py) has been updated to extract the container name from the subdomain with **PRIORITY 1** (checked before Referer or session):

```python
# PRIORITY 1: Extract from subdomain (Host header)
if host and '.desktop.hub.mdg-hamburg.de' in host:
    subdomain = host.split('.desktop.hub.mdg-hamburg.de')[0]
    if subdomain and subdomain != 'desktop':
        container = Container.get_by_proxy_path(subdomain)
```

**This means:**
- `julian-kiedaisch.desktop.hub.mdg-hamburg.de` → looks up container with proxy_path = `julian-kiedaisch`
- Falls back to Referer/session for backward compatibility
- No code changes needed in noVNC or containers!

### 4. Frontend (Optional Enhancement)

The frontend has been updated to automatically redirect users to subdomain URLs when accessing from the main domain:

```javascript
// When user clicks on a desktop:
if (currentHost === 'desktop.hub.mdg-hamburg.de') {
    // Redirect to subdomain
    window.location.href = `https://${proxyPath}.desktop.hub.mdg-hamburg.de/desktop/${proxyPath}`;
}
```

## 🧪 Testing

### Test 1: DNS Resolution

```bash
# Each container should resolve
dig julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de
```

### Test 2: WebSocket Connection

Run the test script:

```bash
python3 test_subdomain_websocket.py
```

Expected output:
```
Response: HTTP/1.1 101 Switching Protocols
✅ ✅ ✅  SUCCESS! ✅ ✅ ✅
Subdomain-based routing WORKS!
```

### Test 3: Browser Access

1. Open: `https://desktop.hub.mdg-hamburg.de`
2. Click on a desktop (e.g., "Ubuntu with VSCode")
3. Browser redirects to: `https://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de/desktop/...`
4. noVNC should connect without error 1005/1006

## 🔧 Container Configuration (If Needed)

If you need to explicitly configure the WebSocket URL in your Kasm containers, update the noVNC configuration:

```javascript
// In the container's noVNC initialization:
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.hostname; // This will be container-name.desktop.hub.mdg-hamburg.de
const wsUrl = `${protocol}//${host}/websockify`;

// Initialize noVNC with the subdomain URL
rfb = new RFB(target, wsUrl);
```

## 📊 URL Mapping Examples

| Container Name | Proxy Path | Subdomain URL |
|---------------|-----------|--------------|
| `julian.kiedaisch-ubuntu-vscode-abc123` | `julian-kiedaisch-ubuntu-vscode` | `julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de` |
| `julian.kiedaisch-ubuntu-desktop-def456` | `julian-kiedaisch-ubuntu-desktop` | `julian-kiedaisch-ubuntu-desktop.desktop.hub.mdg-hamburg.de` |
| `julian.kiedaisch-chromium-ghi789` | `julian-kiedaisch-chromium` | `julian-kiedaisch-chromium.desktop.hub.mdg-hamburg.de` |

## 🎉 Benefits Summary

1. **No WebSocket Configuration Needed**: Works with default noVNC settings
2. **No Cookie Management**: Host header is always sent
3. **No Referer Dependency**: Doesn't rely on blocked headers
4. **Better Security**: Each container gets its own subdomain
5. **Cleaner URLs**: More intuitive structure
6. **SSL Compatible**: Wildcard certificate covers all subdomains
7. **Backward Compatible**: Old path-based URLs still work via fallback

## 🚀 Deployment Steps

1. ✅ **Configure DNS wildcard record**
2. ✅ **Deploy updated apache.conf**
3. ✅ **Reload Apache**
4. ✅ **Restart Flask app** (picks up new routing logic)
5. ✅ **Test with test_subdomain_websocket.py**
6. ✅ **Test in browser**

## 📝 Notes

- The wildcard SSL certificate you already have covers `*.desktop.hub.mdg-hamburg.de`
- Flask code maintains backward compatibility with path-based routing
- No changes needed to existing containers
- Frontend automatically redirects to subdomains when appropriate
- WebSocket connections will "just work" without errors 1005/1006

## 🐛 Troubleshooting

**Issue: "Connection refused"**
- Check DNS: `dig container-name.desktop.hub.mdg-hamburg.de`
- Verify wildcard record is configured

**Issue: "SSL certificate error"**
- Verify your wildcard certificate includes `*.desktop.hub.mdg-hamburg.de`
- Check certificate with: `openssl s_client -connect container-name.desktop.hub.mdg-hamburg.de:443`

**Issue: "Container not found"**
- Check Flask logs: `docker logs <flask-container>`
- Verify container's `proxy_path` matches subdomain
- Check database: `SELECT container_name, proxy_path FROM containers;`

**Issue: Still getting error 1005**
- Confirm Apache ServerAlias is configured: `sudo apache2ctl -S`
- Check Apache is forwarding Host header: `grep Host /var/log/apache2/desktop_access.log`
- Verify Flask receives correct Host: Check Flask debug logs
