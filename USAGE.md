# Usage Examples

This document provides examples of how to use the IServ Remote Desktop API.

## Prerequisites

1. A valid OAuth session ID obtained through the `/login` and `/authorize` flow
2. Docker installed and running on the host
3. The Kasm workspace image pulled: `docker pull kasmweb/ubuntu-focal-desktop:1.15.0`

## Authentication Flow

### 1. Initiate Login
```bash
# Redirect user to login endpoint
curl http://localhost:5006/login
# This will redirect to the OAuth provider (IServ)
```

### 2. After OAuth Callback
```bash
# The user will be redirected to your frontend with a session_id parameter
# Example: http://your-frontend.com/?session_id=abc123-xyz789
```

### 3. Validate Session
```bash
curl -H "X-Session-ID: abc123-xyz789" \
     http://localhost:5006/session
```

## Container Management

### Start a Container

```bash
curl -X POST \
  -H "X-Session-ID: your-session-id" \
  http://localhost:5006/api/container/start
```

Response:
```json
{
  "success": true,
  "message": "Container started successfully",
  "container": {
    "id": "container-uuid",
    "container_name": "kasm-username-session",
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
