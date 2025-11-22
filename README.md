# iserv-remote-desktop
Remote Desktop as docker container with OIDC access

This application provides remote desktop access via Kasm Workspaces in Docker containers, with authentication through OAuth/OIDC (e.g., IServ).

## Features

- OAuth/OIDC authentication (IServ compatible)
- Web-based desktop selection interface
- Multiple desktop types (Ubuntu with VSCode, Ubuntu Desktop, Ubuntu with Chromium)
- Per-user Docker container management
- Automatic Kasm workspace provisioning
- Session-based container lifecycle
- Admin panel for managing all containers
- Real-time container status updates
- Last access timestamps for each desktop
- Automatic cleanup of stopped containers

## Setup

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

6. Run the application:
   ```bash
   python run.py
   ```
   
   Or use Docker Compose:
   ```bash
   docker-compose up
   ```

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

### Frontend Routes
- `GET /` - Desktop selection page (main UI)
- `GET /admin` - Admin panel page (admin users only)

### Authentication
- `GET /login` - Initiate OAuth login
- `GET /authorize` - OAuth callback
- `GET /session` - Validate session
- `POST /logout` - End session

### Container Management
- `POST /api/container/start?desktop_type=<type>` - Start a new container
- `GET /api/container/status` - Get container status
- `POST /api/container/stop` - Stop container
- `POST /api/container/remove` - Remove container
- `GET /api/container/list` - List user's containers

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
- `VNC_PASSWORD`: VNC password for accessing containers
- `DOCKER_HOST_URL`: Host URL for generating access URLs (e.g., `example.com` or `localhost`)

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
The application is configured for production use with nginx:
1. Nginx handles SSL/TLS termination (required for port 443 access)
2. Proper WebSocket support for noVNC connections
3. Access the application through nginx on ports 80 (HTTP) and 443 (HTTPS)
4. **SSL Setup**: See [SSL_SETUP.md](SSL_SETUP.md) for detailed SSL/HTTPS configuration

**Important**: For production environments where only port 443 is accessible, SSL configuration is mandatory. See [SSL_SETUP.md](SSL_SETUP.md) for setup instructions.

## Security Considerations

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

