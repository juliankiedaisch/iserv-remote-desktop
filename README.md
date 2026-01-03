# iserv-remote-desktop
Remote Desktop as docker container with OIDC access

This application provides remote desktop access via Kasm Workspaces in Docker containers, with authentication through OAuth/OIDC (e.g., IServ).

## Architecture

The application uses a **separated frontend-backend architecture**:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  React Frontend │────▶│  Flask Backend  │────▶│ Docker Host     │
│  (Static files) │     │  (API + WS)     │     │ (Containers)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │
         │    WebSocket (WS)     │
         └───────────────────────┘
```

- **Frontend**: React SPA with TypeScript, communicates via REST API and WebSocket
- **Backend**: Flask API server with Socket.IO for real-time updates
- **WebSocket**: Socket.IO for container status updates, flask-sock for VNC proxy

## Features

- OAuth/OIDC authentication (IServ compatible)
- **React-based web interface** with real-time updates
- **Multi-language support** (German and English)
  - Automatic browser language detection
  - Easy language switching with toggle button
  - Easily extensible for additional languages
  - See [I18N_GUIDE.md](I18N_GUIDE.md) for details
- Multiple desktop types (Ubuntu with VSCode, Ubuntu Desktop, Ubuntu with Chromium)
- Per-user Docker container management
- Automatic Kasm workspace provisioning
- Session-based container lifecycle
- Admin panel for managing all containers
- **File Manager** for uploading and downloading files to/from containers
  - Private and public file spaces
  - Drag-and-drop upload support
  - Folder management and navigation
  - See [FILE_MANAGER.md](FILE_MANAGER.md) for details
- **Real-time container status updates via WebSocket**
- Last access timestamps for each desktop
- Automatic cleanup of stopped containers
- **Scalable to 50-100+ concurrent users** (see [SCALABILITY_GUIDE.md](SCALABILITY_GUIDE.md))

## Setup

### Backend Setup

1. Copy `.env.example` to `.env` and configure:
   - OAuth credentials (IServ)
   - Database connection
   - Docker/Kasm settings
   
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure Docker is installed and running on the host

4. Pull the Kasm workspace images:
   ```bash
   docker pull kasmweb/ubuntu-focal-desktop:1.15.0
   docker pull kasmweb/vs-code:1.15.0
   docker pull kasmweb/chromium:1.15.0
   ```

5. Test your installation:
   ```bash
   python3 scripts/test_installation.py
   ```

6. Run the backend:
   ```bash
   python run.py
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment (optional):
   ```bash
   cp .env.example .env
   # Edit .env to set REACT_APP_API_URL if backend is on different host
   ```

4. For development:
   ```bash
   npm start
   ```

5. For production build:
   ```bash
   npm run build
   # Serve the `build` directory with any static file server
   ```

### Docker Compose (Full Stack)

The application provides a complete Docker Compose setup with separate services for the database, backend, and frontend.

#### Prerequisites
1. Docker and Docker Compose installed
2. Configure environment files:
   ```bash
   # Backend configuration
   cp backend/.env.example backend/.env
   # Edit backend/.env with your OAuth credentials and settings
   
   # Frontend configuration (optional)
   cp frontend/.env.example frontend/.env
   # Edit frontend/.env if backend is on different host
   ```

3. Set required environment variables in backend/.env:
   - OAuth credentials (OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, etc.)
   - Database password (POSTGRES_PASSWORD)
   - SECRET_KEY for Flask sessions
   - Frontend URL (FRONTEND_URL)

#### Services
The docker-compose.yml defines three services:

1. **postgres**: PostgreSQL 15 database
   - Stores user sessions, container metadata, and application data
   - Data persisted in named volume

2. **backend**: Python Flask API server
   - Runs on port 5021 (mapped to host)
   - Handles authentication, container management, and WebSocket connections
   - Requires Docker socket access for container operations
   - Reads configuration from backend/.env

3. **frontend**: React application served by nginx
   - Runs on port 3000 (mapped to host)
   - Static files built during Docker image creation
   - Reads configuration from frontend/.env

#### Usage
Start all services:
```bash
docker compose up -d
```

View logs:
```bash
docker compose logs -f
```

Stop all services:
```bash
docker compose down
```

Rebuild after code changes:
```bash
docker compose build
docker compose up -d
```

#### External Apache Proxy
This docker-compose setup is designed to work with an external Apache proxy server (see apache.conf). The services expose ports directly to the host:
- Backend API: Port 5021 → Apache proxies /api and /ws to this port
- Frontend: Port 3000 → Apache proxies / (root) to this port

The Apache server should be configured to proxy requests to these ports on the Docker host machine.

For detailed usage examples, see [USAGE.md](USAGE.md).

## User Interface

### Desktop Selection Page
After logging in, users are presented with a dashboard showing available desktop types:
- **Ubuntu with VSCode** - Full Ubuntu desktop with Visual Studio Code pre-installed
- **Ubuntu Desktop** - Standard Ubuntu desktop environment
- **Ubuntu with Chromium** - Ubuntu desktop with Chromium browser

Each desktop card shows:
- Current status (running/stopped)
- Last access timestamp
- Click to start or connect to the desktop

### Admin Panel
Admin users have access to an admin panel (⚙️ icon in header) where they can:
- View all running containers from all users
- See container statistics (total, running, active users)
- Stop individual containers
- Stop all containers at once
- Remove containers

## API Endpoints

### Authentication
- `GET /api/auth/login` - Initiate OAuth login
- `GET /api/auth/authorize` - OAuth callback
- `GET /api/auth/session` - Validate session
- `POST /api/auth/logout` - End session

### Container Management
- `POST /api/container/start?desktop_type=<type>` - Start a new container
- `GET /api/container/status` - Get container status
- `POST /api/container/stop` - Stop container
- `POST /api/container/remove` - Remove container
- `GET /api/container/list` - List user's containers

### Desktop Proxy
- `GET /api/desktop/<proxy_path>` - Proxy to container desktop
- `WS /api/websockify` - WebSocket proxy for VNC connections

### Admin API (Admin Only)
- `GET /api/admin/containers` - List all containers from all users
- `POST /api/admin/container/<id>/stop` - Stop any container
- `DELETE /api/admin/container/<id>/remove` - Remove any container
- `POST /api/admin/containers/stop-all` - Stop all running containers

All container endpoints require a valid session ID via:
- Query parameter: `?session_id=xxx`
- Header: `X-Session-ID: xxx`
- Authorization header: `Bearer xxx`

## Configuration

See `.env.example` for all available configuration options.

Key Docker/Kasm settings:
- `KASM_IMAGE`: Docker image to use (default: kasmweb/ubuntu-focal-desktop:1.15.0)
- `KASM_CONTAINER_PORT`: Container port (default: 6901)
- `KASM_CONTAINER_PROTOCOL`: Protocol for container connections - `http` or `https` (default: https)
- `KASM_VERIFY_SSL`: Verify SSL certificates when connecting to containers - `true` or `false` (default: false, recommended for self-signed certificates)
- `VNC_USER`: VNC username for authentication (default: kasm_user)
- `VNC_PASSWORD`: VNC password for accessing containers (automatically passed to avoid manual authentication)
- `DOCKER_HOST_URL`: Host URL for generating access URLs (e.g., `example.com` or `localhost`)
- `DOCKER_HOST_PROTOCOL`: Protocol to use for container URLs - `http` or `https` (default: https)

## Container Access Architecture

The application uses a **reverse proxy architecture** with nginx to provide seamless access to Kasm containers:

### URL Structure
Containers are accessed via: `https://{DOCKER_HOST_URL}/desktop/{username}-{desktop-type}`

Examples:
- `https://example.com/desktop/john-ubuntu-vscode`
- `https://example.com/desktop/jane-ubuntu-desktop`
- `https://example.com/desktop/bob-ubuntu-chromium`

### How It Works
1. Each container is assigned:
   - A unique host port (7000-8000 range) for internal communication
   - A unique proxy path (`{username}-{desktop-type}`) for external access
2. Nginx acts as a reverse proxy with proper WebSocket support
3. All requests to `/desktop/*` are forwarded through Flask to the appropriate container port
4. Multiple users can access their containers simultaneously via unique proxy paths

### Production Deployment
The application supports two deployment options:

#### Option 1: With External Apache Proxy (Recommended for existing Apache servers)
If you have an existing Apache server handling SSL/TLS:
1. Apache handles SSL termination and WebSocket proxying on port 443
2. Backend Flask application runs on port 5021 (configured in docker-compose.yml)
3. Frontend React application runs on port 3000 (configured in docker-compose.yml)
4. Access the application through Apache
5. **Apache Setup**: See [APACHE_SETUP.md](APACHE_SETUP.md) for detailed Apache configuration or reference apache.conf

#### Option 2: With Internal Nginx Proxy (Standalone deployment)
For standalone deployments without external proxy:
1. Uncomment the nginx service in `docker-compose.yml`
2. Nginx handles SSL/TLS termination and WebSocket proxying
3. Access the application through nginx on ports 80/443
4. **Nginx Setup**: See [SSL_SETUP.md](SSL_SETUP.md) for detailed configuration

**Important**: For production environments where only port 443 is accessible, proper proxy configuration with WebSocket support is mandatory.

## Security Considerations

### Container SSL/HTTPS and Authentication
Kasm containers typically run with HTTPS and self-signed certificates. The application handles this automatically:
- **SSL Certificate Verification**: By default, SSL certificate verification is disabled for localhost container connections (`KASM_VERIFY_SSL=false`) to support self-signed certificates
- **Automatic VNC Authentication**: VNC credentials are automatically passed via HTTP Basic Auth headers, eliminating the need for users to manually enter passwords
- **Configuration**: Set `KASM_CONTAINER_PROTOCOL=https` (default) and `VNC_PASSWORD` in your `.env` file

### SSL/HTTPS
- **Required for production**: When only port 443 is accessible from the internet
- Ensures secure WebSocket connections for noVNC
- See [SSL_SETUP.md](SSL_SETUP.md) for setup instructions
- Use Let's Encrypt for free, automated certificates

### Docker Socket Access
The application requires access to the Docker socket (`/var/run/docker.sock`) to create and manage containers. This grants significant privileges. For production environments, consider:

1. Using Docker-in-Docker (DinD) instead of socket mounting
2. Implementing a separate container orchestration service with limited permissions
3. Using Kubernetes with appropriate RBAC policies
4. Running the application on a dedicated Docker host with network isolation

### Secrets Management
- Never commit `.env` files with real credentials
- Use environment variables or secrets management tools (e.g., Docker secrets, Kubernetes secrets)
- Rotate VNC passwords regularly
- Use strong, unique passwords for all services

## Troubleshooting

### WebSocket Connection Issues (Code 1006/1005)

If you see errors like "Connection closed (code: 1006)" or "Failed when connecting", or Flask logs show "NOT a WebSocket upgrade request", this is caused by Apache not forwarding WebSocket upgrade headers to Flask.

**Quick Fix:**
1. Update your Apache configuration with WebSocket header forwarding:
   ```apache
   # Add these lines BEFORE ProxyPass directive
   SetEnvIf Upgrade "(?i)websocket" IS_WEBSOCKET=1
   SetEnvIf Connection "(?i)upgrade" IS_UPGRADE=1
   RequestHeader set Upgrade "websocket" env=IS_WEBSOCKET
   RequestHeader set Connection "Upgrade" env=IS_UPGRADE
   ```

2. Test and reload Apache:
   ```bash
   sudo apache2ctl configtest
   sudo systemctl reload apache2
   ```

3. Verify the fix with test script:
   ```bash
   ./scripts/test_apache_websocket_headers.sh localhost:5021 http
   ```

**Detailed Information:**
- [WEBSOCKET_PROXY_FIX_SUMMARY.md](WEBSOCKET_PROXY_FIX_SUMMARY.md) - Complete fix guide with testing
- [WEBSOCKET_FIX_QUICKSTART.md](WEBSOCKET_FIX_QUICKSTART.md) - Quick reference
- [WEBSOCKET_HEADER_FIX.md](WEBSOCKET_HEADER_FIX.md) - Technical explanation
- [APACHE_SETUP.md](APACHE_SETUP.md) - Full Apache configuration guide

**Check if headers are being forwarded:**
```bash
# Watch Flask logs
docker-compose logs -f app | grep websockify

# Expected (GOOD): "WebSocket upgrade request detected"
# Problem (BAD): "NOT a WebSocket upgrade request"
```

### Other Common Issues

For other issues, see:
- [APACHE_SETUP.md](APACHE_SETUP.md) - Apache configuration troubleshooting
- [USAGE.md](USAGE.md) - Usage examples and common scenarios
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures

