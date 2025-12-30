# 🚀 Deployment Checklist: Subdomain-Based WebSocket Fix

## ✅ Pre-Deployment Checklist

- [x] Code changes implemented:
  - [x] [apache.conf](apache.conf) - Added `ServerAlias *.desktop.hub.mdg-hamburg.de`
  - [x] [app/routes/proxy_routes.py](app/routes/proxy_routes.py) - Added subdomain extraction logic
  - [x] Test scripts created

## 📋 Deployment Steps

### Step 1: DNS Configuration
**⏱️ Time:** 5-15 minutes (DNS propagation may take longer)

```bash
# Add wildcard DNS A record in your DNS provider:
# Type: A
# Name: *.desktop.hub.mdg-hamburg.de
# Value: <your-server-ip>
# TTL: 300

# Verify DNS propagation:
dig julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de +short
# Should return: <your-server-ip>
```

**Status:** ⬜ Not started | ⏳ In progress | ✅ Complete

---

### Step 2: Deploy Apache Configuration
**⏱️ Time:** 2-3 minutes

```bash
# On the Apache server (desktop.hub.mdg-hamburg.de):

# Backup current config
sudo cp /etc/apache2/sites-available/desktop.conf /etc/apache2/sites-available/desktop.conf.backup

# Copy new config
sudo cp apache.conf /etc/apache2/sites-available/desktop.conf

# Test configuration
sudo apache2ctl configtest
# Expected output: Syntax OK

# Reload Apache
sudo systemctl reload apache2

# Verify ServerAlias is active
sudo apache2ctl -S | grep desktop.hub.mdg-hamburg.de
# Should show: ServerAlias *.desktop.hub.mdg-hamburg.de
```

**Status:** ⬜ Not started | ⏳ In progress | ✅ Complete

---

### Step 3: Restart Flask Application
**⏱️ Time:** 1-2 minutes

```bash
# On the Docker host (172.22.0.27):
cd /root/iserv-remote-desktop

# Pull latest code if needed
git pull

# Restart containers to pick up new routing logic
docker-compose restart

# Verify Flask is running
docker-compose ps
# Should show: app container running

# Check Flask logs
docker-compose logs -f app
# Look for: "✓ Found container from subdomain: ..."
```

**Status:** ⬜ Not started | ⏳ In progress | ✅ Complete

---

### Step 4: Verify SSL Certificate
**⏱️ Time:** 2 minutes

Your wildcard SSL certificate should already cover `*.desktop.hub.mdg-hamburg.de`. Verify:

```bash
# Test subdomain SSL
openssl s_client -connect julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de:443 -servername julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de < /dev/null 2>&1 | grep -E 'subject=|issuer='

# Expected: Certificate valid for *.desktop.hub.mdg-hamburg.de
```

**Status:** ⬜ Not started | ⏳ In progress | ✅ Complete

---

## 🧪 Testing

### Test 1: DNS Resolution
```bash
cd /root/iserv-remote-desktop

# Test DNS for multiple containers
for container in julian.kiedaisch-ubuntu-vscode john-doe-ubuntu-desktop test-chromium; do
    echo "Testing: $container.desktop.hub.mdg-hamburg.de"
    dig +short $container.desktop.hub.mdg-hamburg.de
done
```

**Expected:** All should return your server IP

**Status:** ⬜ Pass | ❌ Fail

---

### Test 2: Subdomain WebSocket
```bash
cd /root/iserv-remote-desktop
python3 test_subdomain_websocket.py
```

**Expected output:**
```
Response: HTTP/1.1 101 Switching Protocols
✅ ✅ ✅  SUCCESS! ✅ ✅ ✅
```

**Status:** ⬜ Pass | ❌ Fail

---

### Test 3: All Routing Methods
```bash
cd /root/iserv-remote-desktop
python3 test_all_routing_methods.py
```

**Expected output:**
```
Method                         Result               Reliability
----------------------------------------------------------------------
1. Subdomain (Host header)     ✅ PASS              Always sent
2. Referer header              ✅ PASS              Often blocked
3. No container info           ❌ FAIL              Expected failure
```

**Status:** ⬜ Pass | ❌ Fail

---

### Test 4: Browser Test
1. Open: https://desktop.hub.mdg-hamburg.de
2. Log in with OAuth
3. Click on "Ubuntu with VSCode" desktop
4. Browser should redirect to: `https://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de`
5. Desktop should load without error 1005/1006
6. noVNC should connect successfully

**Status:** ⬜ Pass | ❌ Fail

---

## 📊 Post-Deployment Verification

### Check Apache Logs
```bash
# On Apache server
tail -f /var/log/apache2/desktop_access.log | grep -E 'websockify|Upgrade'
```

**Look for:**
- Requests to subdomains: `GET /websockify HTTP/1.1` Host: `container-name.desktop.hub.mdg-hamburg.de`
- HTTP 101 responses: `HTTP/1.1 101 Switching Protocols`

---

### Check Flask Logs
```bash
# On Docker host
docker-compose logs -f app | grep -E 'subdomain|websocket'
```

**Look for:**
- `✓ Found container from subdomain: julian-kiedaisch-ubuntu-vscode -> julian.kiedaisch-ubuntu-vscode-abc123`
- No "Container not found" errors

---

### Check Container Connectivity
```bash
# Verify container is receiving WebSocket connections
docker exec -it <container-name> netstat -an | grep 6901
# Should show ESTABLISHED connections on port 6901
```

---

## 🐛 Troubleshooting

### Issue: DNS not resolving
```bash
# Check DNS configuration
dig *.desktop.hub.mdg-hamburg.de +short
# or
nslookup julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de

# Wait for DNS propagation (can take 5-60 minutes)
```

**Solution:** Wait for DNS propagation or use shorter TTL

---

### Issue: SSL certificate error
```bash
# Verify certificate covers wildcard
openssl x509 -in /etc/ssl/certs/hub.combined -text -noout | grep DNS

# Should show: DNS:*.desktop.hub.mdg-hamburg.de
```

**Solution:** If not covered, update SSL certificate to include wildcard

---

### Issue: "Container not found" in Flask logs
```bash
# Check if proxy_path matches subdomain
docker-compose exec db sqlite3 /data/iserv_remote_desktop.db "SELECT container_name, proxy_path FROM containers;"
```

**Solution:** Ensure `proxy_path` column matches the subdomain format

---

### Issue: Apache not accepting subdomains
```bash
# Verify ServerAlias
sudo apache2ctl -S | grep -A5 desktop.hub.mdg-hamburg.de

# Should show ServerAlias *.desktop.hub.mdg-hamburg.de
```

**Solution:** Check `apache.conf` and reload Apache

---

## 📝 Rollback Plan

If subdomain routing doesn't work:

```bash
# 1. Restore Apache config
sudo cp /etc/apache2/sites-available/desktop.conf.backup /etc/apache2/sites-available/desktop.conf
sudo systemctl reload apache2

# 2. Revert Flask code
git checkout HEAD~1 app/routes/proxy_routes.py
docker-compose restart

# System will fall back to Referer/Cookie-based routing
```

**Note:** Rollback won't break anything - old routing methods are still supported as fallbacks!

---

## ✅ Success Criteria

Deployment is successful when:

1. ✅ DNS resolves all container subdomains
2. ✅ Apache accepts requests to `*.desktop.hub.mdg-hamburg.de`
3. ✅ SSL certificate covers wildcard subdomains
4. ✅ Flask extracts container from Host header
5. ✅ WebSocket test returns HTTP 101
6. ✅ Browser can access desktop without error 1005/1006
7. ✅ noVNC connects successfully
8. ✅ No "Container not found" errors in logs

---

## 📚 Documentation Reference

- [SUBDOMAIN_FIX_QUICKSTART.md](SUBDOMAIN_FIX_QUICKSTART.md) - Quick reference
- [SUBDOMAIN_ROUTING_GUIDE.md](SUBDOMAIN_ROUTING_GUIDE.md) - Complete guide
- [ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md) - Technical details

---

## 🎯 Expected Timeline

| Step | Duration | Dependencies |
|------|----------|--------------|
| DNS Configuration | 5-60 min | DNS provider access |
| Apache Deployment | 2-3 min | SSH access to Apache server |
| Flask Restart | 1-2 min | Docker host access |
| SSL Verification | 2 min | None (already configured) |
| Testing | 5-10 min | All above complete |
| **Total** | **15-80 min** | Mostly waiting for DNS |

---

## 📞 Support

If you encounter issues:

1. Check logs:
   - Apache: `/var/log/apache2/desktop_error.log`
   - Flask: `docker-compose logs -f app`
   - Container: `docker logs <container-name>`

2. Run diagnostic tests:
   - `python3 test_subdomain_websocket.py`
   - `python3 test_all_routing_methods.py`

3. Verify configuration:
   - DNS: `dig <container>.desktop.hub.mdg-hamburg.de`
   - Apache: `sudo apache2ctl -S`
   - Flask: Check routing code in `app/routes/proxy_routes.py`

---

**Last Updated:** 2025-12-30  
**Version:** 1.0  
**Status:** Ready for deployment
