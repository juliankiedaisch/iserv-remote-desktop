# Proxy Architecture Guide

This document describes the updated proxy architecture that simplifies the external Apache configuration by adding an nginx reverse proxy to the docker-compose stack.

## Architecture Overview

### Previous Architecture (Direct Apache Routing)

```
┌─────────────────────────────────────────────────────────────┐
│               Remote Apache Server (Physical)                │
│  - SSL/TLS Termination                                       │
│  - RewriteMap script queries backend API                     │
│  - Direct routing to:                                        │
│    * Backend API (port 5021)                                 │
│    * Frontend (port 3000)                                    │
│    * VNC containers (ports 7000-8000) via RewriteMap        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │     Docker Compose Stack        │
        │                                 │
        │  ┌──────────┐  ┌────────────┐  │
        │  │ Backend  │  │  Frontend  │  │
        │  │ :5021    │  │  :3000     │  │
        │  └──────────┘  └────────────┘  │
        │                                 │
        │  ┌──────────┐                  │
        │  │Postgres  │                  │
        │  └──────────┘                  │
        └─────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │  VNC Desktop Containers         │
        │  (Dynamically created)          │
        │  Published ports: 7000-8000     │
        └─────────────────────────────────┘
```

### New Architecture (with nginx proxy)

```
┌─────────────────────────────────────────────────────────────┐
│               Remote Apache Server (Physical)                │
│  - SSL/TLS Termination (ONLY)                               │
│  - Simple proxy to nginx on port 8080                       │
│  - Preserves Host header for subdomain routing              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────────┐
        │       Docker Compose Stack                  │
        │                                             │
        │  ┌──────────────────────────────────────┐  │
        │  │  Nginx Proxy (port 8080)             │  │
        │  │  - Main domain routing (/, /api, /ws)│  │
        │  │  - VNC subdomain routing via backend │  │
        │  └──────────────────────────────────────┘  │
        │                │                            │
        │                ▼                            │
        │  ┌──────────┐  ┌────────────┐              │
        │  │ Backend  │  │  Frontend  │              │
        │  │ :5021    │  │  :3000     │              │
        │  │ (internal)  │ (internal) │              │
        │  └──────────┘  └────────────┘              │
        │       │                                     │
        │       ▼                                     │
        │  ┌──────────┐                              │
        │  │Postgres  │                              │
        │  │(internal)│                              │
        │  └──────────┘                              │
        └─────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────────┐
        │  VNC Desktop Containers                     │
        │  (Dynamically created)                      │
        │  Published ports: 7000-8000                 │
        │  Accessed via host.docker.internal          │
        └─────────────────────────────────────────────┘
```

## Key Benefits

### 1. Simplified Apache Configuration
- **Before**: Complex RewriteMap with external Python script
- **After**: Simple ProxyPass to single nginx port (8080)
- Apache only handles SSL termination and proxying
- No need for Apache RewriteMap script on remote server

### 2. Centralized Routing Logic
- All routing logic moved to nginx proxy in docker-compose
- Easier to maintain and update
- No need to sync Apache config changes to remote server

### 3. Better Isolation
- Backend and frontend not directly exposed
- Only nginx proxy port (8080) needs to be accessible from Apache
- VNC containers remain dynamically published (required for direct access)

### 4. Flexible Deployment
- Works with existing wildcard SSL certificate
- No changes needed to DNS or SSL setup
- Compatible with existing OAuth/OIDC configuration

## Configuration Details

### Docker Compose Changes

#### New Nginx Proxy Service
```yaml
proxy:
  image: nginx:alpine
  ports:
    - "8080:80"  # Single exposed port
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/conf.d:/etc/nginx/conf.d:ro
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

#### Updated Backend Service
```yaml
backend:
  # No longer exposes port 5021 externally
  extra_hosts:
    - "host.docker.internal:host-gateway"  # For accessing VNC containers
```

#### Updated Frontend Service
```yaml
frontend:
  # No longer exposes port 3000 externally
```

### Nginx Configuration

#### Main Domain (default.conf)
Routes to backend and frontend based on path:
- `/api` → backend:5021
- `/ws` → backend:5021 (WebSocket)
- `/` → frontend:3000

#### VNC Subdomains (vnc-containers.conf)
Routes `desktop-*.hub.mdg-hamburg.de` to backend's container proxy:
- Extracts proxy_path from subdomain
- Proxies to `/container-proxy/{proxy_path}`
- Backend handles container lookup and routing

### Backend Container Proxy

New endpoint: `/container-proxy/<proxy_path>`
- Looks up container by proxy_path in database
- Proxies requests to container via published host port
- Uses `host.docker.internal` to access host ports
- Handles WebSocket upgrades for VNC
- Injects KasmVNC Basic Auth credentials
- Redirects to main domain if container not found

### Apache Configuration

Simplified to single ProxyPass:
```apache
ProxyPass / http://172.22.0.27:8080/ upgrade=any
ProxyPassReverse / http://172.22.0.27:8080/
```

Where `172.22.0.27` is the Docker host IP.

## VNC Container Port Publishing

### Why Containers Still Need Published Ports

VNC containers **must** continue to publish ports (7000-8000) because:
1. Containers are dynamically created outside docker-compose network
2. Backend Flask app needs direct access to container VNC ports
3. Container routing happens through backend proxy using host ports
4. Using `host.docker.internal` allows docker-compose services to access published ports

### How It Works

1. **Container Creation**
   - Backend creates VNC container with published port (e.g., 7001)
   - Container accessible at `host.docker.internal:7001` from docker-compose services

2. **Request Flow**
   - User → `desktop-user-ubuntu.hub.mdg-hamburg.de`
   - Apache → nginx proxy (8080)
   - Nginx → backend `/container-proxy/user-ubuntu`
   - Backend looks up container, finds port 7001
   - Backend proxies to `https://host.docker.internal:7001`
   - Container responds with VNC session

## Environment Variables

### New Variable: DOCKER_HOST_IP
```bash
# In .env file
DOCKER_HOST_IP=host.docker.internal
```

This allows docker-compose services to access published container ports on the host.

## Migration Guide

### For New Deployments

1. Use the new `docker-compose.yml` with nginx proxy
2. Use `apache-simplified.conf` for Apache configuration
3. Set `DOCKER_HOST_IP=host.docker.internal` in `.env`
4. Only expose port 8080 from docker-compose to Apache server

### For Existing Deployments

#### Option 1: Migrate to Nginx Proxy (Recommended)

1. **Update docker-compose.yml**
   ```bash
   # Stop services
   docker-compose down
   
   # Update docker-compose.yml to include nginx proxy
   # Remove port exposures from backend and frontend
   
   # Update .env
   echo "DOCKER_HOST_IP=host.docker.internal" >> .env
   
   # Start with new configuration
   docker-compose up -d
   ```

2. **Update Apache Configuration**
   - Replace `apache.conf` with `apache-simplified.conf`
   - Update port from multiple (3000, 5021) to single (8080)
   - Remove RewriteMap script and rules
   - Reload Apache: `sudo systemctl reload apache2`

3. **Test**
   - Access main domain: `https://desktop.hub.mdg-hamburg.de`
   - Create a VNC container
   - Access via subdomain: `https://desktop-{proxy-path}.hub.mdg-hamburg.de`

#### Option 2: Keep Existing Architecture

If you prefer to keep the current RewriteMap approach:
- Keep using `apache.conf` as-is
- Keep backend port 5021 exposed
- Keep frontend port 3000 exposed
- No changes needed to docker-compose.yml
- The new code is backward compatible

## Troubleshooting

### Nginx Cannot Access Container Ports

**Symptom**: 502 Bad Gateway when accessing VNC subdomain

**Solution**: 
- Ensure `extra_hosts` is set in docker-compose.yml for backend and proxy
- Verify `DOCKER_HOST_IP=host.docker.internal` in `.env`
- Check containers are publishing ports: `docker ps | grep kasm`

### Apache Cannot Reach Nginx Proxy

**Symptom**: 503 Service Unavailable

**Solution**:
- Verify nginx proxy is running: `docker-compose ps proxy`
- Check port 8080 is accessible from Apache server
- Verify firewall rules allow Apache → Docker host:8080

### Subdomain Routing Not Working

**Symptom**: Redirects to main domain instead of VNC

**Solution**:
- Check backend logs: `docker-compose logs backend`
- Verify container has valid proxy_path in database
- Check container status is 'running'
- Verify host_port is assigned

## Performance Considerations

### Benefits
- Single connection from Apache to nginx (connection pooling)
- Nginx efficiently handles static content and routing
- Backend only handles dynamic container proxying

### Limitations
- Additional hop through nginx adds minimal latency (~1-5ms)
- Container proxying goes through backend (unavoidable with dynamic routing)

## Security Notes

### Ports Exposed
- **Port 8080**: Nginx proxy (external, from Apache)
- **Ports 7000-8000**: VNC containers (external, but need authentication)

### Access Control
- VNC containers use Basic Auth (embedded in nginx/backend config)
- OAuth/OIDC authentication required for main application
- Backend validates container ownership before proxying

### SSL/TLS
- SSL termination remains at Apache (remote server)
- Internal communication (nginx ↔ backend ↔ containers) can be HTTP
- Container VNC uses HTTPS with self-signed certificates

## Future Enhancements

Possible improvements for future versions:

1. **Kubernetes Deployment**: Replace docker-compose with K8s
2. **Service Mesh**: Use Istio or Linkerd for advanced routing
3. **Load Balancing**: Multiple nginx replicas for high availability
4. **Container Network**: Move VNC containers to dedicated network
5. **Dynamic Port Allocation**: Use overlay network instead of published ports

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f proxy backend`
2. Verify configuration files in `nginx/conf.d/`
3. Test backend proxy: `curl http://localhost:8080/api/health`
4. Review Apache logs on remote server
