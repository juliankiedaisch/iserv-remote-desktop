# Docker Compose Setup Guide

This document describes the Docker Compose setup for the IServ Remote Desktop application.

## Architecture Overview

The application uses a three-tier architecture with separate services:

```
┌─────────────────────────────────────────────────┐
│           External Apache Proxy                  │
│         (Handles SSL/TLS & Routing)              │
│  - Port 443 (HTTPS)                              │
│  - Routes /api → backend:5021                    │
│  - Routes /ws → backend:5021 (WebSocket)         │
│  - Routes / → frontend:3000                      │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│            Docker Compose Services               │
│                                                  │
│  ┌────────────────┐  ┌────────────────┐         │
│  │   Frontend     │  │    Backend     │         │
│  │   (React)      │  │    (Flask)     │         │
│  │   Port: 3000   │  │   Port: 5021   │         │
│  │   (nginx)      │  │                │         │
│  └────────────────┘  └────────────────┘         │
│           │                  │                   │
│           │                  ▼                   │
│           │          ┌────────────────┐          │
│           │          │   PostgreSQL   │          │
│           │          │   Port: 5432   │          │
│           │          │  (Internal)    │          │
│           │          └────────────────┘          │
│           │                  │                   │
│           └──────────────────┘                   │
└─────────────────────────────────────────────────┘
```

## Services

### 1. PostgreSQL Database
- **Image**: postgres:15-alpine
- **Purpose**: Stores user sessions, container metadata, and application data
- **Port**: 5432 (internal only, not exposed to host)
- **Volume**: postgres_data (persistent storage)
- **Health Check**: pg_isready command

### 2. Backend (Python Flask)
- **Build**: Built from backend/Dockerfile
- **Purpose**: REST API, authentication, container management, WebSocket server
- **Port**: 5021 (exposed to host for Apache proxy)
- **Configuration**: backend/.env
- **Key Features**:
  - OAuth/OIDC authentication
  - Docker container lifecycle management
  - Socket.IO for real-time updates
  - File upload/download management
- **Dependencies**: PostgreSQL database
- **Special Requirements**: Access to Docker socket (/var/run/docker.sock)

### 3. Frontend (React + nginx)
- **Build**: Built from frontend/Dockerfile (multi-stage build)
- **Purpose**: User interface served as static files
- **Port**: 3000 (exposed to host for Apache proxy)
- **Configuration**: frontend/.env
- **Build Process**:
  1. Node.js stage: npm install and npm run build
  2. Nginx stage: Serve static files with React Router support

## Configuration

### Environment Files

#### Backend (.env)
Located at `backend/.env`, copy from `backend/.env.example`:

**Required Variables:**
- `SECRET_KEY`: Flask session secret
- `POSTGRES_PASSWORD`: Database password
- `OAUTH_CLIENT_ID`: OAuth client ID
- `OAUTH_CLIENT_SECRET`: OAuth client secret
- `OAUTH_AUTHORIZE_URL`: OAuth authorization endpoint
- `OAUTH_TOKEN_URL`: OAuth token endpoint
- `OAUTH_USERINFO_URL`: OAuth user info endpoint
- `OAUTH_JWKS_URI`: OAuth JWKS URI
- `OAUTH_REDIRECT_URI`: OAuth redirect URI
- `FRONTEND_URL`: Frontend URL (e.g., https://desktop.example.com)

**Optional Variables:**
- `DEBUG`: Enable debug mode (default: False)
- `FLASK_ENV`: Flask environment (default: production)
- `POSTGRES_USER`: Database user (default: scratch4school)
- `POSTGRES_DB`: Database name (default: scratch4school)
- `KASM_IMAGE`: Docker image for workspaces
- `VNC_USER`: VNC username
- `VNC_PASSWORD`: VNC password
- See backend/.env.example for complete list

#### Frontend (.env)
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
- Backend connects to PostgreSQL via hostname `postgres:5432`
- Frontend → Backend communication happens through the external Apache proxy
- Containers use the connection string from DATABASE_URI environment variable

## Volume Mounts

### Backend Service
- `/var/run/docker.sock:/var/run/docker.sock` - Docker socket for container management (⚠️ requires elevated privileges)
- `./data:/data` - Persistent user data directory
- `./backend/uploads:/app/uploads` - File uploads directory

### PostgreSQL Service
- `postgres_data:/var/lib/postgresql/data` - Named volume for database persistence

## Integration with Apache

This docker-compose setup is designed to work with an external Apache proxy server. The Apache configuration (see `apache.conf`) should:

1. **SSL/TLS Termination**: Handle HTTPS on port 443
2. **Backend Proxying**: 
   - Proxy `/api/*` to `http://<docker-host>:5021/api/`
   - Proxy `/ws/*` to `http://<docker-host>:5021/ws/` with WebSocket upgrade
3. **Frontend Proxying**: 
   - Proxy `/` to `http://<docker-host>:3000/`
4. **Container Subdomain Routing**: Handle dynamic subdomain routing for desktop containers

Example Apache proxy configuration:
```apache
# Backend API
ProxyPass /api http://172.22.0.27:5021/api upgrade=any
ProxyPassReverse /api http://172.22.0.27:5021/api

# Backend WebSocket
ProxyPass /ws http://172.22.0.27:5021/ws upgrade=websocket
ProxyPassReverse /ws http://172.22.0.27:5021/ws

# Frontend
ProxyPass / http://172.22.0.27:3000/
ProxyPassReverse / http://172.22.0.27:3000/
```

Replace `172.22.0.27` with your Docker host IP address.

## Troubleshooting

### Service Won't Start
```bash
# Check service logs
docker compose logs backend

# Check if port is already in use
sudo netstat -tlnp | grep 5021

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
