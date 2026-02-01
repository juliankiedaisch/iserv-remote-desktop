# Traefik Deployment Guide

This guide provides step-by-step instructions for deploying the Traefik-based direct routing implementation.

## Prerequisites

- Docker and Docker Compose installed on Docker server
- Access to proxy server for nginx configuration
- Access to backend server for environment variable updates
- Backup of current configurations

## Deployment Steps

### Step 1: Create Docker Network

On the **Docker server** (where containers run):

```bash
# Create the kasm_proxy network
docker network create \
  --driver=bridge \
  --subnet=192.168.100.0/24 \
  --gateway=192.168.100.1 \
  kasm_proxy

# Verify network creation
docker network ls | grep kasm_proxy
docker network inspect kasm_proxy
```

### Step 2: Deploy Traefik

On the **Docker server**:

```bash
# Navigate to repository directory
cd /path/to/iserv-remote-desktop

# Deploy Traefik
docker-compose -f traefik-docker-compose.yml up -d

# Verify Traefik is running
docker ps | grep traefik

# Check Traefik logs
docker logs traefik-kasm-router
```

Expected output:
```
time="..." level=info msg="Configuration loaded from flags."
time="..." level=info msg="Starting provider *docker.Provider"
time="..." level=info msg="Traefik version 3.0"
```

### Step 3: Update Backend Configuration

On the **Backend server** (172.22.0.27):

```bash
# Navigate to backend directory
cd /path/to/iserv-remote-desktop

# Backup current .env
cp .env .env.backup

# Add Traefik configuration to .env
cat >> .env << 'EOF'

# Traefik Configuration (added for Variante 3)
TRAEFIK_ENABLED=true
TRAEFIK_NETWORK=kasm_proxy
TRAEFIK_DOMAIN=hub.mdg-hamburg.de
DOCKER_SERVER_IP=172.22.0.28

# Authentication
DASHBOARD_AUTH_URL=https://dashboard.hub.mdg-hamburg.de/approvals/check
EOF

# Restart backend to apply changes
docker-compose restart backend

# Verify backend is running
docker-compose ps
docker-compose logs backend | tail -20
```

### Step 4: Update Proxy Configuration

On the **Proxy server** (nginx/OpenResty):

```bash
# Navigate to nginx configuration directory
cd /etc/nginx  # or wherever nginx.conf is located

# Backup current nginx.conf
cp nginx.conf nginx.conf.backup-lua-$(date +%Y%m%d)

# Copy new Traefik-based configuration
# (You'll need to manually copy nginx.conf.traefik from the repository)
cp /path/to/iserv-remote-desktop/nginx.conf.traefik nginx.conf

# Test nginx configuration
nginx -t

# If test passes, reload nginx
nginx -s reload

# Verify nginx reloaded successfully
systemctl status nginx
# or
service nginx status
```

### Step 5: Create Test Container

Via the web interface:

1. Log in to the dashboard
2. Navigate to container creation
3. Select a desktop type
4. Click "Create Container"
5. Wait for container to be created

### Step 6: Verify Traefik Routing

Check that the container has Traefik labels:

```bash
# On Docker server
# Find the container name (e.g., kasm_username_ubuntu-desktop)
docker ps --format "table {{.Names}}\t{{.Status}}"

# Inspect container labels
docker inspect kasm_username_ubuntu-desktop | jq '.[0].Config.Labels'
```

Expected labels:
```json
{
  "traefik.enable": "true",
  "traefik.http.routers.kasm-username-ubuntu-desktop.rule": "Host(`test-desktop-username-ubuntu-desktop-token.hub.mdg-hamburg.de`)",
  "traefik.http.routers.kasm-username-ubuntu-desktop.entrypoints": "web",
  "traefik.http.services.kasm-username-ubuntu-desktop.loadbalancer.server.port": "6901",
  "traefik.docker.network": "kasm_proxy"
}
```

Check network connectivity:
```bash
# Verify container is on kasm_proxy network
docker inspect kasm_username_ubuntu-desktop | jq '.[0].NetworkSettings.Networks'
```

### Step 7: Test Access

1. Open browser and navigate to the container URL (shown in web interface)
2. Should be redirected to authentication if not logged in
3. After authentication, should see VNC desktop
4. Verify WebSocket connection works (try interacting with desktop)

### Step 8: Monitor

Check logs for any issues:

```bash
# Traefik logs (on Docker server)
docker logs -f traefik-kasm-router

# Backend logs (on backend server)
docker-compose logs -f backend

# Nginx logs (on proxy server)
tail -f /var/log/nginx/test-desktop_vnc_combined.log
tail -f /var/log/nginx/error.log
```

## Verification Checklist

- [ ] kasm_proxy network created
- [ ] Traefik container running
- [ ] Backend environment variables updated
- [ ] Backend restarted successfully
- [ ] Nginx configuration updated
- [ ] Nginx reloaded without errors
- [ ] Test container created successfully
- [ ] Container has Traefik labels
- [ ] Container accessible via subdomain
- [ ] WebSocket connection works
- [ ] Authentication still functions

## Troubleshooting

### Container Not Accessible (503 Error)

**Check 1:** Traefik is running
```bash
docker ps | grep traefik
```

**Check 2:** Container has labels
```bash
docker inspect {container_name} | jq '.[0].Config.Labels'
```

**Check 3:** Container is on kasm_proxy network
```bash
docker inspect {container_name} | jq '.[0].NetworkSettings.Networks'
```

**Check 4:** Traefik can reach container
```bash
curl -H "Host: test-desktop-user-xxx.hub.mdg-hamburg.de" http://172.22.0.28
```

### Authentication Fails

**Check 1:** Dashboard auth endpoint is accessible
```bash
curl -v https://dashboard.hub.mdg-hamburg.de/approvals/check
```

**Check 2:** Nginx auth_request location is configured
```bash
grep -A5 "auth-check-internal" /etc/nginx/nginx.conf
```

**Check 3:** Cookies are being forwarded
```bash
grep "Cookie" /etc/nginx/nginx.conf
```

### WebSocket Fails

**Check 1:** Upgrade headers are set
```bash
grep -A2 "Upgrade" /etc/nginx/nginx.conf
```

**Check 2:** Proxy buffering is disabled
```bash
grep "proxy_buffering" /etc/nginx/nginx.conf
```

### Backend Not Creating Labels

**Check 1:** TRAEFIK_ENABLED is set to true
```bash
docker-compose exec backend env | grep TRAEFIK
```

**Check 2:** Check backend logs during container creation
```bash
docker-compose logs backend | grep -i traefik
```

Should see: "Traefik labels generated for subdomain: ..."

## Rollback Procedure

If issues occur, you can rollback:

### Rollback Backend
```bash
cd /path/to/iserv-remote-desktop

# Restore original .env
cp .env.backup .env

# Restart backend
docker-compose restart backend
```

### Rollback Nginx
```bash
cd /etc/nginx

# Restore original configuration
cp nginx.conf.backup-lua-YYYYMMDD nginx.conf

# Test and reload
nginx -t && nginx -s reload
```

### Stop Traefik (optional)
```bash
docker-compose -f traefik-docker-compose.yml down
```

Note: Existing containers created without Traefik labels will continue to work with the old Lua-based routing.

## Performance Monitoring

### Metrics to Monitor

1. **Traefik response times**
   ```bash
   docker logs traefik-kasm-router | grep -i "duration"
   ```

2. **Backend container creation**
   ```bash
   docker-compose logs backend | grep "Container.*created successfully"
   ```

3. **Nginx proxy times**
   ```bash
   tail -f /var/log/nginx/test-desktop_vnc_combined.log
   ```

4. **Network usage**
   ```bash
   docker stats traefik-kasm-router
   ```

## Gradual Migration

To gradually migrate existing containers:

1. **Phase 1:** Deploy Traefik, keep TRAEFIK_ENABLED=false
2. **Phase 2:** Enable for new containers only
3. **Phase 3:** Let old containers naturally expire
4. **Phase 4:** Optionally recreate remaining old containers

## Support

For issues:
1. Check logs (Traefik, Backend, Nginx)
2. Refer to `docs/TRAEFIK_ARCHITECTURE.md` troubleshooting section
3. Review `SECURITY_SUMMARY.md` for security considerations
4. Contact system administrator

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-01  
**Deployment Status:** Ready for Production
