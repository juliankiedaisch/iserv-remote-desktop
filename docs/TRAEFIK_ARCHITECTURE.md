# Traefik-based Direct Routing Architecture (Variante 3)

## Overview

This document describes the Traefik-based direct routing architecture for Kasm containers, implemented as "Variante 3". This hybrid approach optimizes network traffic by having the proxy server handle authentication while traffic flows directly to the Docker server via Traefik.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│              https://test-desktop-user-xxx.hub.mdg-hamburg.de    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTPS (SSL)
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Proxy Server (OpenResty/Nginx)                │
│                                                                   │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │  1. SSL Termination  │────▶│  2. Auth Check       │          │
│  │     (Port 443)       │     │     (auth_request)   │          │
│  └──────────────────────┘     └──────────┬───────────┘          │
│                                           │                      │
│                     ┌─────────────────────┴──────────┐           │
│                     │  3. Inject Basic Auth Header   │           │
│                     │     Authorization: Basic ...   │           │
│                     └─────────────────────┬──────────┘           │
│                                           │                      │
│                     ┌─────────────────────┴──────────┐           │
│                     │  4. Proxy to Docker Server     │           │
│                     │     http://172.22.0.28:80      │           │
│                     └─────────────────────┬──────────┘           │
└───────────────────────────────────────────┼──────────────────────┘
                                            │
                                            │ HTTP (Internal)
                                            │ + Host header preserved
                                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Docker Server (172.22.0.28)                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                     Traefik (Port 80)                       │  │
│  │                                                             │  │
│  │  ┌──────────────────┐     ┌───────────────────────────┐   │  │
│  │  │  5. Read Host    │────▶│  6. Match Container       │   │  │
│  │  │     Header       │     │     by Label Rules        │   │  │
│  │  └──────────────────┘     └───────────┬───────────────┘   │  │
│  │                                        │                   │  │
│  │                     ┌──────────────────┴──────────────┐    │  │
│  │                     │  7. Route to Container:6901     │    │  │
│  │                     └─────────────────────────────────┘    │  │
│  └────────────────────────────────────────┼───────────────────┘  │
│                                            │                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    kasm_proxy Network                        │ │
│  │               (192.168.100.0/24)                             │ │
│  │                                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │ │
│  │  │  Container 1 │  │  Container 2 │  │  Container N │      │ │
│  │  │  Kasm VNC    │  │  Kasm VNC    │  │  Kasm VNC    │      │ │
│  │  │  :6901       │  │  :6901       │  │  :6901       │      │ │
│  │  │              │  │              │  │              │      │ │
│  │  │ Traefik      │  │ Traefik      │  │ Traefik      │      │ │
│  │  │ Labels       │  │ Labels       │  │ Labels       │      │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Proxy Server (OpenResty/Nginx)

**Location:** External-facing server  
**Configuration:** `nginx.conf.traefik`

**Responsibilities:**
- SSL/TLS termination
- Authentication via backend container access check endpoint
- Basic Auth header injection for Kasm containers
- Proxy traffic to Docker server's Traefik

**Key Configuration:**
```nginx
location = /auth-check-internal {
    internal;
    # Forward auth request to backend
    proxy_pass http://172.22.0.27:5021/api/container-access-check;
    proxy_set_header Cookie $http_cookie;
    proxy_set_header Host $host;
}

location / {
    # Check authentication
    auth_request /auth-check-internal;
    
    # Proxy to Docker server Traefik
    proxy_pass http://172.22.0.28;
    
    # Set Basic Auth for Kasm
    proxy_set_header Authorization "Basic a2FzbV91c2VyOnBhc3N3b3Jk";
    
    # Preserve hostname for Traefik routing
    proxy_set_header Host $host;
    
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
}
```

### 2. Docker Server with Traefik

**Location:** 172.22.0.28  
**Configuration:** `traefik-docker-compose.yml`

**Responsibilities:**
- Container discovery via Docker labels
- Dynamic routing based on Host header
- Load balancing (if needed)
- Automatic service registration/deregistration

**Key Configuration:**
```yaml
services:
  traefik:
    image: traefik:latest
    command:
      - "--providers.docker=true"
      - "--providers.docker.network=kasm_proxy"
      - "--entrypoints.web.address=:80"
    networks:
      kasm_proxy:
        ipv4_address: 192.168.100.50
```

### 3. Backend (Python/Flask)

**Location:** 172.22.0.27:5021  
**Service:** `backend/app/services/docker_manager.py` and `backend/app/routes/apache_api_routes.py`

**Responsibilities:**
- Authentication and access control via `/api/container-access-check` endpoint
- Create containers with Traefik labels
- Connect containers to kasm_proxy network
- Generate subdomain URLs
- Container lifecycle management

**Key Methods/Endpoints:**
- `/api/container-access-check`: Authenticates users and checks container access permissions
  - Owners have access to their containers
  - Teachers and admins have access to all containers
- `_generate_traefik_labels()`: Generates routing labels
- `create_container()`: Creates containers with labels
- `get_container_url()`: Returns correct subdomain URL

## Traffic Flow

### 1. Initial Request

```
User Browser → https://test-desktop-user-abc.hub.mdg-hamburg.de/
```

### 2. Proxy Server Processing

```
Nginx:
1. Receives HTTPS request on port 443
2. Executes auth_request to /auth-check-internal
3. Checks authentication at backend: http://172.22.0.27:5021/api/container-access-check
   - Backend validates session cookie
   - Backend checks if user is owner, teacher, or admin
4. If auth OK, injects Basic Auth header
5. Proxies to http://172.22.0.28 (Traefik)
6. Preserves Host header: test-desktop-user-abc.hub.mdg-hamburg.de
```

### 3. Traefik Routing

```
Traefik:
1. Receives HTTP request from proxy
2. Reads Host header: test-desktop-user-abc.hub.mdg-hamburg.de
3. Matches against container labels:
   traefik.http.routers.{safe_name}.rule=Host(`test-desktop-user-abc.hub.mdg-hamburg.de`)
4. Routes to matched container on port 6901
```

### 4. Container Response

```
Kasm Container:
1. Receives request on port 6901
2. Authenticates via Basic Auth header
3. Returns VNC/WebSocket content
4. Response flows back through Traefik → Proxy → User
```

## Container Label Schema

Each container created by the backend includes these Traefik labels:

```python
{
    # Enable routing for this container
    "traefik.enable": "true",
    
    # Router rule - matches by hostname
    "traefik.http.routers.{safe_name}.rule": "Host(`{subdomain}.hub.mdg-hamburg.de`)",
    
    # Use 'web' entrypoint (port 80)
    "traefik.http.routers.{safe_name}.entrypoints": "web",
    
    # Service name reference
    "traefik.http.routers.{safe_name}.service": "{safe_name}",
    
    # Container port for VNC
    "traefik.http.services.{safe_name}.loadbalancer.server.port": "6901",
    
    # Network to use
    "traefik.docker.network": "kasm_proxy",
}
```

### Example Labels for User "john.doe"

```python
{
    "traefik.enable": "true",
    "traefik.http.routers.kasm-john-doe-ubuntu.rule": "Host(`test-desktop-john-doe-ubuntu-xyz123.hub.mdg-hamburg.de`)",
    "traefik.http.routers.kasm-john-doe-ubuntu.entrypoints": "web",
    "traefik.http.routers.kasm-john-doe-ubuntu.service": "kasm-john-doe-ubuntu",
    "traefik.http.services.kasm-john-doe-ubuntu.loadbalancer.server.port": "6901",
    "traefik.docker.network": "kasm_proxy",
}
```

## Network Topology

### Network: kasm_proxy

**Subnet:** 192.168.100.0/24  
**Gateway:** 192.168.100.1  
**Type:** Bridge network

**Connected Services:**
- Traefik: 192.168.100.50 (static IP)
- Kasm Containers: Dynamic IPs (192.168.100.2-254)

**Creation:**
```bash
docker network create \
  --driver=bridge \
  --subnet=192.168.100.0/24 \
  --gateway=192.168.100.1 \
  kasm_proxy
```

## Environment Variables

### Backend (.env)

```bash
# Traefik Configuration
TRAEFIK_ENABLED=true
TRAEFIK_NETWORK=kasm_proxy
TRAEFIK_DOMAIN=hub.mdg-hamburg.de
DOCKER_SERVER_IP=172.22.0.28

# Container Prefix for Subdomain
CONTAINER_PREFIX=test-desktop

# Authentication
DASHBOARD_AUTH_URL=https://dashboard.hub.mdg-hamburg.de/approvals/check
```

## Migration from Lua-based Routing

### Old Architecture (Lua)
- Nginx queries backend API for each request
- Backend returns container IP:port
- Nginx proxies directly to container
- All traffic flows through proxy server

### New Architecture (Traefik)
- Nginx authenticates and proxies to Docker server
- Traefik uses labels for routing
- No API query needed per request
- Reduced load on proxy server

### Migration Steps

1. **Deploy Traefik on Docker server:**
   ```bash
   cd /path/to/iserv-remote-desktop
   docker-compose -f traefik-docker-compose.yml up -d
   ```

2. **Create kasm_proxy network (if not exists):**
   ```bash
   docker network create --subnet=192.168.100.0/24 --gateway=192.168.100.1 kasm_proxy
   ```

3. **Update backend environment:**
   ```bash
   # Add to .env
   TRAEFIK_ENABLED=true
   TRAEFIK_NETWORK=kasm_proxy
   ```

4. **Deploy updated backend:**
   ```bash
   docker-compose restart backend
   ```

5. **Update proxy nginx configuration:**
   ```bash
   cp nginx.conf nginx.conf.backup-lua
   cp nginx.conf.traefik nginx.conf
   # Reload nginx
   nginx -t && nginx -s reload
   ```

6. **Test with new containers:**
   - Create a new container via the web interface
   - Verify it gets Traefik labels
   - Verify it's accessible via subdomain

7. **Migrate existing containers (optional):**
   - Let existing containers naturally expire
   - Or recreate them with `docker rm -f` and restart via UI

## Troubleshooting

### Container Not Accessible

**Symptom:** 503 Service Unavailable or connection timeout

**Checks:**
1. Verify Traefik is running:
   ```bash
   docker ps | grep traefik
   ```

2. Check container has correct labels:
   ```bash
   docker inspect {container_name} | jq '.[0].Config.Labels'
   ```

3. Verify container is on kasm_proxy network:
   ```bash
   docker inspect {container_name} | jq '.[0].NetworkSettings.Networks'
   ```

4. Check Traefik logs:
   ```bash
   docker logs traefik-kasm-router
   ```

5. Test Traefik routing:
   ```bash
   curl -H "Host: test-desktop-user-xxx.hub.mdg-hamburg.de" http://172.22.0.28
   ```

### Authentication Fails

**Symptom:** 401 Unauthorized or 403 Forbidden

**Checks:**
1. Verify backend auth endpoint is accessible:
   ```bash
   curl -v http://172.22.0.27:5021/api/container-access-check
   ```

2. Check backend logs for authentication errors:
   ```bash
   docker-compose logs backend | grep "Container access check"
   ```

3. Verify session cookie is valid:
   - Check that user is logged in via OAuth
   - Check session hasn't expired
   
4. Check nginx logs on proxy server:
   ```bash
   tail -f /var/log/nginx/test-desktop_vnc_combined.log
   ```

5. Verify cookies are being forwarded:
   ```nginx
   proxy_set_header Cookie $http_cookie;
   ```

6. For 403 Forbidden errors, check access permissions:
   - Container owner always has access
   - Teachers (role='teacher') have access to all containers
   - Admins (role='admin') have access to all containers
   - Other users are denied access

### WebSocket Connection Fails

**Symptom:** VNC loads but doesn't connect, or disconnects immediately

**Checks:**
1. Verify WebSocket headers are set in nginx:
   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection $connection_upgrade;
   ```

2. Check proxy buffering is disabled:
   ```nginx
   proxy_buffering off;
   ```

3. Verify timeouts are sufficient:
   ```nginx
   proxy_read_timeout 1800s;
   ```

### Container Not Getting Labels

**Symptom:** Container created but Traefik doesn't route to it

**Checks:**
1. Verify TRAEFIK_ENABLED is set:
   ```bash
   echo $TRAEFIK_ENABLED
   ```

2. Check backend logs during container creation:
   ```bash
   docker logs iserv-remote-desktop-backend-1
   ```

3. Verify _generate_traefik_labels() is being called:
   - Look for log line: "Traefik labels generated for subdomain: ..."

## Performance Considerations

### Benefits
- **Reduced Proxy Load:** Proxy only handles auth, not data transfer
- **Direct Routing:** Traffic flows directly from proxy to containers
- **Auto-Discovery:** No API queries needed for routing
- **Scalability:** Traefik can handle many more routes efficiently

### Trade-offs
- **Additional Component:** Traefik adds complexity
- **Network Overhead:** One additional hop (proxy → Traefik → container)
- **Label Management:** Must ensure labels are correct

### Expected Performance
- **Latency:** +1-2ms for Traefik routing (negligible)
- **Throughput:** No impact (Traefik is highly optimized)
- **Concurrent Users:** Can handle 100+ concurrent VNC sessions

## Security Considerations

### Authentication Flow
1. User authenticates via OAuth (IServ)
2. Session cookie is stored in browser
3. For each container access request:
   - Nginx calls backend `/api/container-access-check` endpoint via auth_request
   - Backend validates session cookie
   - Backend checks container ownership and user role
   - Access granted if: user is owner, teacher, or admin
4. Only authenticated and authorized requests reach Docker server
5. Traefik itself doesn't handle auth (by design)

### Access Control
- **Container Owners:** Full access to their own containers
- **Teachers (role='teacher'):** Access to all containers (for supervision/support)
- **Admins (role='admin'):** Access to all containers (for administration)
- **Students:** Only access to their own containers

### Network Isolation
- kasm_proxy network is internal only
- Containers can't access host network
- Only Traefik exposes port 80 to proxy server

### Basic Auth
- Kasm containers require Basic Auth
- Credentials injected by proxy server
- Not exposed to end users

### SSL/TLS
- SSL terminates at proxy server
- Internal traffic is HTTP (within trusted network)
- Can be upgraded to HTTPS if needed

## Adding New Container Types

To add a new desktop type with Traefik routing:

1. **Define in database:** Add to desktop_images table

2. **No routing changes needed:** Traefik auto-discovers via labels

3. **Test subdomain:** Should work automatically with pattern:
   ```
   test-desktop-{username}-{desktop_type}-{token}.hub.mdg-hamburg.de
   ```

## Maintenance

### Regular Checks
- Monitor Traefik logs for routing errors
- Verify containers are being created with correct labels
- Check kasm_proxy network health
- Review nginx logs for auth failures

### Backup Configuration
- nginx.conf.traefik (proxy server)
- traefik-docker-compose.yml (Docker server)
- .env (backend environment)

### Rolling Updates
1. Update backend code
2. Restart backend service
3. New containers get new labels
4. Existing containers continue working
5. Gradually replace old containers

## References

- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Docker Labels](https://docs.docker.com/config/labels-custom-metadata/)
- [Nginx auth_request](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html)
