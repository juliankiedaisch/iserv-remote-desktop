# 🎯 Quick Start: Subdomain-Based WebSocket Fix

## The Problem
WebSocket error 1005/1006 because noVNC can't send session cookies → Flask can't find container

## The Solution  
Use subdomains! `container-name.desktop.hub.mdg-hamburg.de`

**Why it works:** Host header is ALWAYS sent (no cookies/Referer needed!)

## 3-Step Deployment

### 1️⃣ Configure DNS
```bash
# Add wildcard DNS record:
*.desktop.hub.mdg-hamburg.de  A  <your-server-ip>

# Test:
dig julian.kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de
```

### 2️⃣ Deploy Apache Config
```bash
# apache.conf already updated with:
# ServerAlias *.desktop.hub.mdg-hamburg.de

sudo cp apache.conf /etc/apache2/sites-available/desktop.conf
sudo systemctl reload apache2
```

### 3️⃣ Restart Flask
```bash
# Flask routing code already updated to extract container from subdomain
docker-compose restart
```

## ✅ Test It
```bash
python3 test_subdomain_websocket.py
```

Expected: `HTTP/1.1 101 Switching Protocols ✅`

## 📝 What Changed

### Apache ([apache.conf](/root/iserv-remote-desktop/apache.conf))
- Added: `ServerAlias *.desktop.hub.mdg-hamburg.de`

### Flask ([app/routes/proxy_routes.py](/root/iserv-remote-desktop/app/routes/proxy_routes.py))
- PRIORITY 1: Extract container from Host header subdomain
- PRIORITY 2: Fall back to Referer (backward compat)
- PRIORITY 3: Fall back to session cookie (backward compat)

### Frontend (Optional - [app/templates/index.html](/root/iserv-remote-desktop/app/templates/index.html))
- Auto-redirects to subdomains from main domain

## 🎉 Result

Users access: `https://desktop.hub.mdg-hamburg.de`  
→ Click desktop  
→ Redirected to: `https://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de`  
→ noVNC connects via: `wss://julian-kiedaisch-ubuntu-vscode.desktop.hub.mdg-hamburg.de/websockify`  
→ **WebSocket works!** No cookies/Referer needed! ✨

## 📚 Full Documentation
See [SUBDOMAIN_ROUTING_GUIDE.md](/root/iserv-remote-desktop/SUBDOMAIN_ROUTING_GUIDE.md) for complete details.
