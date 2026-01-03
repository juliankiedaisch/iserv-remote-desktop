# Docker Compose Setup Guide

This document describes the Docker Compose setup for the IServ Remote Desktop application.

## Architecture Overview

The application uses a multi-tier architecture with an nginx reverse proxy handling internal routing:

```
┌─────────────────────────────────────────────────────────────┐
│           External Apache Proxy (Remote Server)             │
│         (Handles SSL/TLS Termination Only)                   │
│  - Port 443 (HTTPS)                                         │
│  - Simple proxy to nginx on port 8080                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│            Docker Compose Services                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Nginx Proxy (Port: 8080, exposed)                   │  │
│  │  - Main domain routing (/, /api, /ws)                │  │
│  │  - VNC subdomain routing (desktop-*.domain.com)      │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌────────────────┐  ┌────────────────┐                    │
│  │   Frontend     │  │    Backend     │                    │
│  │   (React)      │  │    (Flask)     │                    │
│  │   Port: 3000   │  │   Port: 5021   │                    │
│  │   (internal)   │  │   (internal)   │                    │
│  └────────────────┘  └────────────────┘                    │
│           │                  │                              │
│           │                  ▼                              │
│           │          ┌────────────────┐                     │
│           │          │   PostgreSQL   │                     │
│           │          │   Port: 5432   │                     │
│           │          │  (Internal)    │                     │
│           │          └────────────────┘                     │
│           │                  │                              │
│           └──────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │  VNC Desktop Containers                 │
        │  (Dynamically created)                  │
        │  Published ports: 7000-8000             │
        └─────────────────────────────────────────┘
```

## Services

### 1. PostgreSQL Database
- **Image**: postgres:17-alpine
- **Purpose**: Stores user sessions, container metadata, and application data
- **Port**: 5432 (internal only, not exposed to host)
- **Volume**: postgres_data (persistent storage)
- **Health Check**: pg_isready command

### 2. Backend (Python Flask)
- **Image**: teacherki/mdg-desktop-backend:latest or built from backend/Dockerfile
- **Purpose**: REST API, authentication, container management, WebSocket server, container proxy
- **Port**: 5021 (internal only, accessed via nginx proxy)
- **Configuration**: .env in project root
- **Key Features**:
  - OAuth/OIDC authentication
  - Docker container lifecycle management
  - Socket.IO for real-time updates
  - File upload/download management
  - Container proxy for VNC subdomain routing
- **Dependencies**: PostgreSQL database
- **Special Requirements**: 
  - Access to Docker socket (/var/run/docker.sock)
  - Access to host network via host.docker.internal (for VNC containers)

### 3. Frontend (React + nginx)
- **Image**: teacherki/mdg-desktop-frontend:latest or built from frontend/Dockerfile
- **Purpose**: User interface served as static files
- **Port**: 3000 (internal only, accessed via nginx proxy)
- **Configuration**: .env in project root
- **Build Process** (when building from Dockerfile):
  1. Node.js stage: npm install and npm run build
  2. Nginx stage: Serve static files with React Router support

### 4. Nginx Proxy (NEW)
- **Image**: nginx:alpine
- **Purpose**: Reverse proxy for all services, handles routing logic
- **Port**: 8080 (exposed to host for external Apache proxy)
- **Configuration**: nginx/nginx.conf and nginx/conf.d/*.conf
- **Key Features**:
  - Routes main domain requests to backend/frontend
  - Routes VNC subdomain requests to backend's container proxy
  - Handles WebSocket upgrades
  - Simplifies external Apache configuration
- **Special Requirements**: Access to host network via host.docker.internal (for VNC containers)

## Configuration

### Environment Files

#### Root .env File
Located at `.env` in project root, copy from `.env.example`:

**Required Variables:**
- `SECRET_KEY`: Flask session secret
- `APACHE_API_KEY`: API key for Apache RewriteMap (if using old architecture)
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_DB`: Database name
- `POSTGRES_SERVER_NAME`: Database hostname (default: postgres)
- `OAUTH_CLIENT_ID`: OAuth client ID
- `OAUTH_CLIENT_SECRET`: OAuth client secret
- `OAUTH_AUTHORIZE_URL`: OAuth authorization endpoint
- `OAUTH_TOKEN_URL`: OAuth token endpoint
- `OAUTH_USERINFO_URL`: OAuth user info endpoint
- `OAUTH_JWKS_URI`: OAuth JWKS URI
- `OAUTH_REDIRECT_URI`: OAuth redirect URI
- `FRONTEND_URL`: Frontend URL (e.g., https://desktop.example.com)

**Important Variables for New Architecture:**
- `DOCKER_HOST_IP`: IP address for accessing published container ports (default: host.docker.internal)
  - Use `host.docker.internal` when running in Docker
  - Use actual host IP (e.g., 172.22.0.27) when running outside Docker

**Optional Variables:**
- `DEBUG`: Enable debug mode (default: False)
- `FLASK_ENV`: Flask environment (default: production)
- `ROLE_ADMIN`: IServ group name for admin role
- `ROLE_TEACHER`: IServ group name for teacher role
- `USER_DATA_BASE_DIR`: Base directory for user data (default: /data/users)
- `SHARED_PUBLIC_DIR`: Shared public directory (default: /data/shared/public)
- See .env.example for complete list

#### Legacy Frontend .env (Optional)
Located at `frontend/.env`, copy from `frontend/.env.example`:

**Optional Variables:**
- `REACT_APP_API_URL`: Backend API URL (leave empty for same-origin)
- `REACT_APP_WS_URL`: WebSocket URL (leave empty for same-origin)

### Docker Compose Environment
Create a `.env` file in the root directory for docker-compose variables:
```bash
POSTGRES_USER=scratch4school
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=scratch4school
```

## Usage

### Starting Services
```bash
# Start all services in detached mode
docker compose up -d

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f backend
```

### Stopping Services
```bash
# Stop all services (preserves volumes)
docker compose down

# Stop and remove volumes (WARNING: deletes database)
docker compose down -v
```

### Rebuilding After Code Changes
```bash
# Rebuild all images
docker compose build

# Rebuild specific service
docker compose build backend

# Rebuild and restart
docker compose up -d --build
```

### Viewing Status
```bash
# Show running services
docker compose ps

# Show resource usage
docker stats
```

### Accessing Logs
```bash
# All services
docker compose logs

# Follow logs in real-time
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Specific service
docker compose logs backend
```

## Network Configuration

The services communicate via a Docker bridge network called `app-network`. Within this network:
- Nginx proxy connects to backend via hostname `backend:5021`
- Nginx proxy connects to frontend via hostname `frontend:3000`
- Backend connects to PostgreSQL via hostname `postgres:5432`
- Backend and nginx proxy access VNC containers via `host.docker.internal` (published ports)
- External Apache connects to nginx proxy on host port 8080

## Volume Mounts

### Nginx Proxy Service
- `./nginx/nginx.conf:/etc/nginx/nginx.conf:ro` - Main nginx configuration
- `./nginx/conf.d:/etc/nginx/conf.d:ro` - Server block configurations

### Backend Service
- `/var/run/docker.sock:/var/run/docker.sock` - Docker socket for container management (⚠️ requires elevated privileges)
- `./data:/data` - Persistent user data directory
- `./backend/uploads:/app/uploads` - File uploads directory

### PostgreSQL Service
- `postgres_data:/var/lib/postgresql/data` - Named volume for database persistence

## Integration with Apache

This docker-compose setup is designed to work with an external Apache proxy server.

### Recommended Setup (New Architecture)

Use the simplified Apache configuration (`apache-simplified.conf`):

1. **SSL/TLS Termination**: Handle HTTPS on port 443
2. **Simple Proxy to Nginx**: Proxy all requests to nginx on port 8080

Example Apache configuration:
```apache
<VirtualHost *:443>
    ServerName desktop.hub.mdg-hamburg.de
    ServerAlias desktop-*.hub.mdg-hamburg.de

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/hub.combined
    SSLCertificateKeyFile /etc/ssl/private/hub.key

    # Simple proxy to internal nginx service
    ProxyPass / http://172.22.0.27:8080/ upgrade=any
    ProxyPassReverse / http://172.22.0.27:8080/
</VirtualHost>
```

Replace `172.22.0.27` with your Docker host IP address.

### Legacy Setup (Old Architecture)

If you prefer the old architecture with Apache RewriteMap, see the original `apache.conf`.
This requires exposing backend (5021) and frontend (3000) ports directly.

For detailed information about the proxy architecture, see [PROXY_ARCHITECTURE.md](PROXY_ARCHITECTURE.md).

## Troubleshooting

### Service Won't Start
```bash
# Check service logs
docker compose logs proxy
docker compose logs backend

# Check if port is already in use
sudo netstat -tlnp | grep 8080

# Rebuild image
docker compose build backend
docker compose up -d backend
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Verify DATABASE_URI in backend/.env
```

### Frontend Build Fails
```bash
# Check Node.js version compatibility
docker compose build frontend --no-cache

# View build output
docker compose build frontend
```

### Can't Access Through Apache
1. Verify Apache proxy configuration
2. Check firewall rules on Docker host
3. Ensure ports 5021 and 3000 are accessible from Apache server
4. Check Apache logs for proxy errors

### Docker Socket Permission Denied
```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Or run with sudo
sudo docker compose up -d
```

## Security Considerations

### Docker Socket Access
The backend service requires access to `/var/run/docker.sock` to create and manage containers. This grants significant privileges. For production:
- Consider using Docker-in-Docker (DinD)
- Use a dedicated Docker host with network isolation
- Implement appropriate firewall rules

### Environment Variables
- Never commit `.env` files to version control
- Use strong passwords for all services
- Rotate secrets regularly
- Consider using Docker secrets or external secret management

### Network Security
- The PostgreSQL port (5432) is not exposed to the host
- Only backend (5021) and frontend (3000) are accessible from outside
- Use Apache with SSL/TLS for encrypted connections
- Configure firewall rules to restrict access to ports 5021 and 3000

## Maintenance

### Backup Database
```bash
# Create backup
docker compose exec postgres pg_dump -U scratch4school scratch4school > backup.sql

# Restore backup
docker compose exec -T postgres psql -U scratch4school scratch4school < backup.sql
```

### Update Images
```bash
# Pull latest base images
docker compose pull

# Rebuild with new base images
docker compose build --pull

# Restart services
docker compose up -d
```

### Clean Up
```bash
# Remove stopped containers
docker compose rm

# Remove unused images
docker image prune

# Remove unused volumes (WARNING: deletes data)
docker volume prune
```

## Migration from Old Setup

If you're migrating from the old single Dockerfile setup:

1. **Backup your data**:
   ```bash
   # Backup database
   docker compose exec postgres pg_dump -U scratch4school scratch4school > backup.sql
   ```

2. **Stop old services**:
   ```bash
   docker compose down
   ```

3. **Update configuration**:
   - Move backend configuration to `backend/.env`
   - Create `frontend/.env` if needed
   - Update Apache configuration to use new ports (5021, 3000)

4. **Start new services**:
   ```bash
   docker compose up -d
   ```

5. **Restore data** if needed:
   ```bash
   docker compose exec -T postgres psql -U scratch4school scratch4school < backup.sql
   ```

## Additional Resources

- [README.md](README.md) - Main project documentation
- [apache.conf](apache.conf) - Apache proxy configuration reference
- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed architecture documentation
- [FILE_MANAGER.md](FILE_MANAGER.md) - File management features
