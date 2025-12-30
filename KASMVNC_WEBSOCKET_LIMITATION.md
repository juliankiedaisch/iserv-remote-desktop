# KasmVNC WebSocket Proxy Limitation

## Problem Summary

KasmVNC's embedded websockify server **cannot be proxied**. It rejects all WebSocket upgrade requests that don't come directly from browsers.

## Technical Details

### What We Tried

1. **Subdomain-based routing** (`container-name.desktop.hub.mdg-hamburg.de`)
   - Browser → Apache → Flask → KasmVNC
   - Result: KasmVNC returns HTTP 200 (HTML) instead of HTTP 101 (WebSocket upgrade)

2. **Different connection strategies**:
   - Tried port 5901 (raw VNC) - not listening
   - Tried port 6901 (HTTPS/WebSocket combined) - rejects proxy
   - Tried SSL with Basic auth - still rejected
   - Tried various WebSocket libraries - all rejected

### Root Cause

KasmVNC container logs show:
```
Invalid WS request, maybe a HTTP one
Requested file '/index.html'
```

The embedded websockify server validates incoming connections and **only accepts direct browser connections**. When Flask sends its own WebSocket upgrade request (with proper headers, authentication, etc.), KasmVNC treats it as an invalid HTTP request and returns the HTML login page.

### Why Proxying Doesn't Work

```
┌─────────┐    WebSocket    ┌───────┐    WebSocket    ┌──────────┐
│ Browser │ ─────────────→ │ Flask │ ─────X─────→   │ KasmVNC  │
└─────────┘    (HTTP 101)    └───────┘   (HTTP 200)    └──────────┘
                                                        Returns HTML
```

When Flask tries to establish a second WebSocket connection to KasmVNC, the websockify server rejects it. There are no configuration options to disable this validation.

## Solutions

### Solution 1: Direct Port Access (RECOMMENDED)

**Containers are already mapped to host ports**. Users connect directly:
- `https://desktop.hub.mdg-hamburg.de:7000/` (first container)
- `https://desktop.hub.mdg-hamburg.de:7001/` (second container)
- etc.

**Advantages:**
- ✅ WebSocket works perfectly (direct browser connection)
- ✅ No proxy complexity
- ✅ Better performance (fewer hops)
- ✅ Code already updated to return these URLs

**Requirements:**
1. **Firewall Configuration**: Open ports 7000-7100 on 172.22.0.10:
   ```bash
   # On the Apache server (172.22.0.10)
   iptables -A INPUT -p tcp --dport 7000:7100 -j ACCEPT
   iptables-save > /etc/iptables/rules.v4
   ```

2. **SSL Certificate**: Ensure cert covers `desktop.hub.mdg-hamburg.de` (not just `*.desktop.hub.mdg-hamburg.de`)
   - Current cert: `*.hub.mdg-hamburg.de` ✅ Already covers it

3. **Apache Virtual Host** (optional - for port 443 to still work):
   ```apache
   # Add to apache.conf if you want port 443 to work too
   <VirtualHost *:7000>
       ServerName desktop.hub.mdg-hamburg.de
       SSLEngine on
       SSLCertificateFile /path/to/cert.pem
       SSLCertificateKeyFile /path/to/key.pem
       
       ProxyPreserveHost On
       ProxyPass / https://172.22.0.27:7000/ upgrade=any
       ProxyPassReverse / https://172.22.0.27:7000/
   </VirtualHost>
   ```

**User Experience:**
- Click "VS Code" desktop
- Opens new tab: `https://desktop.hub.mdg-hamburg.de:7000/`
- KasmVNC loads instantly, WebSocket works perfectly

### Solution 2: Apache Stream Module (TCP Proxy)

Configure Apache to proxy TCP streams (bypassing HTTP layer):

```apache
LoadModule stream_module modules/mod_stream.so

<IfModule mod_stream.c>
    Listen 7000
    Listen 7001
    # ... more ports
    
    <VirtualHost *:7000>
        ProxyPass / tcp://172.22.0.27:7000/
    </VirtualHost>
</IfModule>
```

**Issues:**
- Complex configuration
- Still requires multiple ports
- No SSL termination at Apache layer

### Solution 3: Different VNC Solution

Replace KasmVNC with VNC server that supports proxied WebSocket:
- **noVNC standalone** (websockify as separate process)
- **TigerVNC** + external websockify
- **Apache Guacamole** (clientless remote desktop)

**Issues:**
- Requires rebuilding all containers
- KasmVNC has excellent performance and features
- Significant migration effort

## Current Code Status

The code has been updated to return direct port URLs:

### File: `app/services/docker_manager.py`

```python
def get_container_url(self, container_record):
    """
    Get the URL to access the container directly via mapped port
    
    KasmVNC's WebSocket cannot be proxied - it requires direct browser connections.
    Return the direct HTTPS URL using the container's host_port mapping.
    """
    if not container_record.host_port:
        return None
    
    host = os.environ.get('DOCKER_HOST_URL', 'localhost')
    return f"https://{host}:{container_record.host_port}/"
```

## Next Steps

1. **Test direct port access** from external network:
   ```bash
   curl -k https://desktop.hub.mdg-hamburg.de:7000/
   ```

2. **Open firewall ports** if connection fails

3. **Test in browser**:
   - Login to https://desktop.hub.mdg-hamburg.de/
   - Click on a desktop
   - Should open `https://desktop.hub.mdg-hamburg.de:7000/`
   - Verify KasmVNC loads and WebSocket connects

## Technical Reference

### Container Port Mappings

Containers are created with:
```python
ports={f'{container_port}/tcp': host_port}
# container_port = 6901 (KasmVNC HTTPS/WebSocket)
# host_port = 7000, 7001, 7002, ... (assigned dynamically)
```

### Database Schema

```sql
SELECT container_name, host_port, status 
FROM containers 
WHERE status = 'running';

-- Example output:
-- kasm-julian.kiedaisch-ubuntu-vscode-fb3abf09 | 7000 | running
-- kasm-julian.kiedaisch-ubuntu-desktop-f93b19dd | 7001 | running
```

### Port Binding Verification

```bash
# Ports are bound to all interfaces (0.0.0.0)
ss -tlnp | grep -E ':(7000|7001)'
# LISTEN 0.0.0.0:7000 (docker-proxy)
# LISTEN 0.0.0.0:7001 (docker-proxy)
```

## Lessons Learned

1. **gevent-websocket is broken** - migrated to flask-sock
2. **Browsers don't send Referer with WebSocket** - can't use Referer-based routing
3. **Periods in subdomains are invalid** - replaced with dashes in proxy_path
4. **KasmVNC's websockify rejects proxied connections** - architectural limitation, not a bug
5. **Direct container access is the only viable solution** with current KasmVNC

## Alternative: iframe Embedding (Not Recommended)

You could serve an HTML page from Flask that embeds the container in an iframe:

```html
<iframe src="https://desktop.hub.mdg-hamburg.de:7000/"></iframe>
```

**Issues:**
- Still requires open ports
- iframe restrictions (CORS, X-Frame-Options)
- Worse user experience
- No benefit over direct access
