# Usage Examples

This document provides examples of how to use the IServ Remote Desktop application, both through the web interface and the API.

## Using the Web Interface

### 1. Login
Navigate to your application URL (e.g., `http://localhost:5020`) and click on the login button or visit `/login`. You'll be redirected to your OAuth provider (IServ) for authentication.

### 2. Desktop Selection
After successful authentication, you'll be redirected to the desktop selection page showing available desktop types:

- **Ubuntu with VSCode** - Full development environment with VSCode
- **Ubuntu Desktop** - Standard Ubuntu desktop
- **Ubuntu with Chromium** - Desktop with Chromium browser

Each desktop card displays:
- Current status (🟢 Running or ⚫ Stopped)
- Last access time (if previously used)

### 3. Starting a Desktop
Click on any desktop card to:
- Start a new container (if not running)
- Connect to an existing container (if already running)

The desktop will open in a new browser tab showing the VNC interface.

### 4. Admin Panel (Admin Users Only)
Admin users will see a ⚙️ icon in the header. Click it to access the admin panel where you can:
- View all running containers across all users
- See statistics (total containers, running containers, active users)
- Stop individual containers
- Stop all containers at once
- Remove containers

### 5. Logout
Click the "Logout" button in the header to end your session.

## API Usage

### Prerequisites

1. A valid OAuth session ID obtained through the `/login` and `/authorize` flow
2. Docker installed and running on the host
3. Kasm workspace images pulled:
   ```bash
   docker pull kasmweb/ubuntu-focal-desktop:1.15.0
   docker pull kasmweb/vs-code:1.15.0
   docker pull kasmweb/chromium:1.15.0
   ```

## Authentication Flow

### 1. Initiate Login
```bash
# Redirect user to login endpoint
curl http://localhost:5020/login
# This will redirect to the OAuth provider (IServ)
```

### 2. After OAuth Callback
```bash
# The user will be redirected to your frontend with a session_id parameter
# Example: http://localhost:5020/?session_id=abc123-xyz789
```

### 3. Validate Session
```bash
curl -H "X-Session-ID: abc123-xyz789" \
     http://localhost:5020/session
```

## Container Management

### Start a Container with Desktop Type

```bash
# Start Ubuntu with VSCode
curl -X POST \
  -H "X-Session-ID: your-session-id" \
  "http://localhost:5020/api/container/start?desktop_type=ubuntu-vscode"

# Start Ubuntu Desktop
curl -X POST \
  -H "X-Session-ID: your-session-id" \
  "http://localhost:5020/api/container/start?desktop_type=ubuntu-desktop"

# Start Ubuntu with Chromium
curl -X POST \
  -H "X-Session-ID: your-session-id" \
  "http://localhost:5020/api/container/start?desktop_type=ubuntu-chromium"
```

Response:
```json
{
  "success": true,
  "message": "Container started successfully",
  "container": {
    "id": "container-uuid",
    "container_name": "kasm-username-ubuntu-vscode-session",
    "desktop_type": "ubuntu-vscode",
    "status": "running",
    "host_port": 7001,
    "created_at": "2024-01-01T12:00:00",
    "started_at": "2024-01-01T12:00:05"
  },
  "url": "http://localhost:7001"
}
```

### Get Container Status

```bash
curl -H "X-Session-ID: your-session-id" \
     http://localhost:5006/api/container/status
```

Response:
```json
{
  "success": true,
  "has_container": true,
  "container": {
    "id": "container-uuid",
    "status": "running",
    "host_port": 7001
  },
  "status": {
    "status": "running",
    "docker_status": "running",
    "host_port": 7001
  },
  "url": "http://localhost:7001"
}
```

### Stop a Container

```bash
curl -X POST \
  -H "X-Session-ID: your-session-id" \
  http://localhost:5006/api/container/stop
```

Response:
```json
{
  "success": true,
  "message": "Container stopped successfully"
}
```

### Remove a Container

```bash
curl -X DELETE \
  -H "X-Session-ID: your-session-id" \
  http://localhost:5006/api/container/remove
```

Response:
```json
{
  "success": true,
  "message": "Container removed successfully"
}
```

### List All User's Containers

```bash
curl -H "X-Session-ID: your-session-id" \
     http://localhost:5006/api/container/list
```

Response:
```json
{
  "success": true,
  "containers": [
    {
      "id": "container-uuid",
      "container_name": "kasm-username-session",
      "status": "running",
      "host_port": 7001,
      "url": "http://localhost:7001"
    }
  ]
}
```

## Accessing the Remote Desktop

Once a container is started, you can access the remote desktop by:

1. Opening the URL returned in the response (e.g., `http://localhost:7001`)
2. Using the VNC password configured in your `.env` file (default: "password")
3. The Kasm workspace will load in your browser

## Automated Cleanup

To automatically clean up old containers and expired sessions:

```bash
# Run the cleanup script
python3 scripts/cleanup.py

# Or set up a cron job (runs every hour)
0 * * * * cd /path/to/iserv-remote-desktop && python3 scripts/cleanup.py
```

## Using with JavaScript/Frontend

```javascript
// Start a container
async function startDesktop(sessionId) {
  const response = await fetch('http://localhost:5006/api/container/start', {
    method: 'POST',
    headers: {
      'X-Session-ID': sessionId
    }
  });
  
  const data = await response.json();
  if (data.success) {
    // Open the desktop in a new window
    window.open(data.url, '_blank');
  }
}

// Check container status
async function checkStatus(sessionId) {
  const response = await fetch('http://localhost:5006/api/container/status', {
    headers: {
      'X-Session-ID': sessionId
    }
  });
  
  const data = await response.json();
  return data;
}

// Stop container
async function stopDesktop(sessionId) {
  const response = await fetch('http://localhost:5006/api/container/stop', {
    method: 'POST',
    headers: {
      'X-Session-ID': sessionId
    }
  });
  
  return await response.json();
}
```

## Admin API (Admin Users Only)

### List All Containers

```bash
curl -H "X-Session-ID: admin-session-id" \
     http://localhost:5020/api/admin/containers
```

Response:
```json
{
  "success": true,
  "containers": [
    {
      "id": "container-uuid",
      "username": "john.doe",
      "container_name": "kasm-john-ubuntu-vscode-abc123",
      "desktop_type": "ubuntu-vscode",
      "status": "running",
      "host_port": 7001,
      "created_at": "2024-01-01T12:00:00",
      "last_accessed": "2024-01-01T14:30:00",
      "url": "http://localhost:7001"
    }
  ]
}
```

### Stop a Specific Container

```bash
curl -X POST \
  -H "X-Session-ID: admin-session-id" \
  http://localhost:5020/api/admin/container/container-uuid/stop
```

### Remove a Specific Container

```bash
curl -X DELETE \
  -H "X-Session-ID: admin-session-id" \
  http://localhost:5020/api/admin/container/container-uuid/remove
```

### Stop All Running Containers

```bash
curl -X POST \
  -H "X-Session-ID: admin-session-id" \
  http://localhost:5020/api/admin/containers/stop-all
```

Response:
```json
{
  "success": true,
  "message": "Stopped 5 containers",
  "stopped_count": 5
}
```

## Troubleshooting

### Container fails to start

1. Check Docker is running: `docker ps`
2. Check the image is available: `docker images | grep kasm`
3. Check available ports: `netstat -an | grep LISTEN`
4. Check application logs for errors

### Cannot access desktop URL

1. Verify the container is running: `docker ps`
2. Check port mapping: `docker port <container-name>`
3. Ensure firewall allows the port
4. Verify DOCKER_HOST_URL is set correctly in `.env`

### Session expired errors

1. Check session validity: `GET /session`
2. Re-authenticate if needed: `GET /login`
3. Verify token refresh is working in logs
