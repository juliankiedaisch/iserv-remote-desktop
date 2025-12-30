# Architecture Comparison: Path-Based vs Subdomain-Based Routing

## 🔴 OLD: Path-Based Routing (BROKEN)

```
Browser                    Apache                    Flask                  Container
  |                          |                         |                        |
  |-- wss://desktop.hub../websockify -------------->  |                        |
  |    Host: desktop.hub...                           |                        |
  |    (NO Referer - blocked by browser!)             |                        |
  |                          |                         |                        |
  |                          |-- Upgrade: websocket -->|                        |
  |                          |                         |                        |
  |                          |                         |-- Find container?      |
  |                          |                         |    ❌ No Host info     |
  |                          |                         |    ❌ No Referer       |
  |                          |                         |    ❌ No Cookie        |
  |                          |                         |                        |
  |                          |                         |-- Close WebSocket      |
  |                          |<------ 101 + Close -----|    (error 1011)       |
  |<-------------------------|                         |                        |
  |                                                                              |
  |-- Browser shows ERROR 1005 ❌                                               |
```

**Problems:**
- ❌ Referer header blocked by browser security
- ❌ Cookies not sent with WebSocket by default
- ❌ No way to identify container

---

## 🟢 NEW: Subdomain-Based Routing (WORKS!)

```
Browser                                Apache                                Flask                  Container
  |                                      |                                     |                        |
  |-- wss://julian-..desktop.hub../websockify ----------------------->        |                        |
  |    Host: julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de       |                        |
  |    ✅ Host header ALWAYS sent!                                            |                        |
  |                                      |                                     |                        |
  |                                      |-- Upgrade: websocket -------------->|                        |
  |                                      |    Host: julian-k...desktop.hub... |                        |
  |                                      |                                     |                        |
  |                                      |                                     |-- Extract subdomain    |
  |                                      |                                     |    = "julian-k..."     |
  |                                      |                                     |                        |
  |                                      |                                     |-- Find container       |
  |                                      |                                     |    by proxy_path       |
  |                                      |                                     |    ✅ Found it!        |
  |                                      |                                     |                        |
  |                                      |                                     |-- Connect to container->|
  |                                      |                                     |                     localhost:7000
  |                                      |<----------- 101 Switching Protocols |                        |
  |<-------------------------------------|                                     |                        |
  |                                                                                                    |
  |-- WebSocket established ✅                                                                         |
  |                                                                                                    |
  |<-- noVNC session starts ------------------------------------------------------------------->      |
```

**Advantages:**
- ✅ Host header **always sent** (HTTP specification)
- ✅ No Referer dependency
- ✅ No Cookie dependency
- ✅ No special WebSocket configuration needed
- ✅ Works with wildcard SSL certificate
- ✅ Clean, predictable URLs

---

## URL Format Comparison

### Path-Based (Old)
```
Main:     https://desktop.hub.mdg-hamburg.de/
Desktop:  https://desktop.hub.mdg-hamburg.de/desktop/julian-kiedaisch-ubuntu-vscode
WebSocket: wss://desktop.hub.mdg-hamburg.de/websockify
           └─ ❌ No container info in Host header!
```

### Subdomain-Based (New)
```
Main:     https://desktop.hub.mdg-hamburg.de/
Desktop:  https://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de/desktop/julian-kiedaisch-ubuntu-vscode
WebSocket: wss://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de/websockify
           └─ ✅ Container info in Host header!
```

---

## Header Comparison

### Path-Based Request (Browser blocks Referer!)
```http
GET /websockify HTTP/1.1
Host: desktop.hub.mdg-hamburg.de          ← Generic domain (no container info)
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Origin: https://desktop.hub.mdg-hamburg.de
(NO Referer - browser security blocks it)
(NO Cookie - noVNC doesn't send it)

Result: Flask can't identify container ❌
```

### Subdomain-Based Request (Always works!)
```http
GET /websockify HTTP/1.1
Host: julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de  ← Container in subdomain! ✅
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Origin: https://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de

Result: Flask extracts "julian-kiedaisch-ubuntu-vscode" from Host ✅
```

---

## Implementation Details

### DNS Configuration
```
Type: A
Name: *.desktop.hub.mdg-hamburg.de
Value: <your-server-ip>
TTL: 300

Effect: All subdomains resolve to your server
- julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de → server
- john-doe-chromium.desktop.hub.mdg-hamburg.de → server
- any-container-name.desktop.hub.mdg-hamburg.de → server
```

### Apache Configuration
```apache
<VirtualHost *:443>
    ServerName desktop.hub.mdg-hamburg.de
    ServerAlias *.desktop.hub.mdg-hamburg.de    ← Accepts all subdomains
    
    # Wildcard SSL certificate covers *.desktop.hub.mdg-hamburg.de
    SSLCertificateFile /etc/ssl/certs/hub.combined
    
    # Forward all requests to Flask
    ProxyPass / http://172.22.0.27:5020/ upgrade=any
    ProxyPassReverse / http://172.22.0.27:5020/
</VirtualHost>
```

### Flask Routing Logic
```python
# Extract Host header
host = request.headers.get('Host', '')
# Example: "julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de"

# Extract subdomain
if '.desktop.hub.mdg-hamburg.de' in host:
    subdomain = host.split('.desktop.hub.mdg-hamburg.de')[0]
    # subdomain = "julian-kiedaisch-ubuntu-vscode"
    
    # Find container
    container = Container.get_by_proxy_path(subdomain)
    # ✅ Found!
```

---

## Routing Priority

Flask now checks in this order:

1. **🥇 Subdomain** (from Host header)
   - Always reliable
   - Always sent
   - Main method

2. **🥈 Referer** (from Referer header)
   - Backward compatibility
   - Often blocked
   - Fallback #1

3. **🥉 Session** (from Cookie)
   - Backward compatibility
   - Often not sent
   - Fallback #2

---

## Migration Path

### Phase 1: Deploy (No Breaking Changes)
1. Add DNS wildcard record
2. Deploy Apache config with ServerAlias
3. Deploy Flask code with subdomain support
4. Old URLs still work via fallback

### Phase 2: Transition
1. Frontend starts redirecting to subdomains
2. Users gradually move to subdomain URLs
3. Both methods work simultaneously

### Phase 3: Cleanup (Optional)
1. Remove Referer/Cookie fallbacks
2. All users on subdomain URLs
3. Simpler, more reliable code

---

## Security Considerations

### Subdomain Isolation
Each container gets its own subdomain, providing:
- **Better cookie isolation** (cookies scoped to subdomain)
- **Clearer audit trails** (logs show which container)
- **CORS boundaries** (each subdomain is separate origin)

### DNS Security
- Wildcard DNS is safe (standard practice)
- SSL wildcard certificate already covers this
- No additional attack surface

### No Breaking Changes
- Backward compatible with existing deployments
- Fallback to old methods if needed
- Gradual migration possible

---

## Performance

### DNS
- Wildcard DNS = same performance as individual records
- Modern DNS caching handles this efficiently

### SSL
- Wildcard certificate = no extra overhead
- Single certificate covers all subdomains

### Flask
- Subdomain extraction = simple string split
- Faster than regex on Referer
- No database lookup for session

**Result: Better performance than old method!**
