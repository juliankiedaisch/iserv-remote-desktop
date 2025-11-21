# iserv-remote-desktop
Remote Desktop as docker container with OIDC access

This application provides remote desktop access via Kasm Workspaces in Docker containers, with authentication through OAuth/OIDC (e.g., IServ).

## Features

- OAuth/OIDC authentication (IServ compatible)
- Per-user Docker container management
- Automatic Kasm workspace provisioning
- Session-based container lifecycle
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

4. Run the application:
   ```bash
   python run.py
   ```

## API Endpoints

### Authentication
- `GET /login` - Initiate OAuth login
- `GET /authorize` - OAuth callback
- `GET /session` - Validate session
- `POST /logout` - End session

### Container Management
- `POST /api/container/start` - Start a new container
- `GET /api/container/status` - Get container status
- `POST /api/container/stop` - Stop container
- `POST /api/container/remove` - Remove container
- `GET /api/container/list` - List user's containers

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
- `DOCKER_HOST_URL`: Host URL for generating access URLs

## Security Considerations

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

