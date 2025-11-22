# Reverse Proxy Architecture - Deployment Guide

## Overview

This application uses a reverse proxy architecture to allow multiple users to access their Kasm desktop containers simultaneously through clean, user-friendly URLs.

## Architecture

### Traditional Approach (Before)
- Each container exposed on a unique port: `http://localhost:7001`, `http://localhost:7002`, etc.
- Problems:
  - Users need to know/remember port numbers
  - Doesn't work for remote users (localhost isn't accessible)
  - Port management complexity
  - Firewall rules needed for each port

### New Reverse Proxy Approach (After)
- All containers accessed through proxy paths: `http://{HOST}/desktop/{username}-{desktop-type}`
- Benefits:
  - Single entry point (standard HTTP port 80/443)
  - Clean, memorable URLs
  - Works for remote users
  - Easy firewall configuration
  - Better security (ports not exposed)

## URL Structure

### Format
```
http://{DOCKER_HOST_URL}/desktop/{username}-{desktop-type}
```

### Examples
```
http://myserver.com/desktop/alice-ubuntu-vscode
http://myserver.com/desktop/bob-ubuntu-desktop
http://myserver.com/desktop/charlie-ubuntu-chromium
```

### Components
- **{DOCKER_HOST_URL}**: Your server's domain or IP (set in `.env`)
- **{username}**: The authenticated user's username
- **{desktop-type}**: One of:
  - `ubuntu-vscode` - Ubuntu with VSCode
  - `ubuntu-desktop` - Standard Ubuntu desktop
  - `ubuntu-chromium` - Ubuntu with Chromium browser

## Deployment Options

### Option 1: Flask Built-in Proxy (Development/Small Scale)

This option uses Flask's built-in reverse proxy for simplicity.

**Pros:**
- Simple setup
- No additional services required
- Good for development and testing

**Cons:**
- Limited WebSocket performance
- Lower concurrent connection capacity
- Not recommended for production

**Setup:**
1. Configure `.env`:
   ```bash
   DOCKER_HOST_URL=your-domain.com
   ```

2. Start the application:
   ```bash
   docker-compose up
   ```

3. Access containers at:
   ```
   http://your-domain.com:5006/desktop/{username}-{desktop-type}
   ```

### Option 2: Nginx Reverse Proxy (Production/Recommended)

This option uses nginx for proper WebSocket support and better performance.

**Pros:**
- Excellent WebSocket support (required for noVNC)
- High performance and scalability
- SSL/TLS termination
- Better logging and monitoring
- Production-ready

**Cons:**
- Slightly more complex setup

**Setup:**

1. Configure `.env`:
   ```bash
   DOCKER_HOST_URL=your-domain.com
   ```

2. Edit `docker-compose.yml` and uncomment the nginx service:
   ```yaml
   nginx:
     image: nginx:alpine
     ports:
       - "80:80"
       - "443:443"  # If using SSL
     volumes:
       - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
       # - ./ssl:/etc/nginx/ssl:ro  # If using SSL
     depends_on:
       - app
     networks:
       - app-network
     restart: unless-stopped
   ```

3. (Optional) For SSL, update `nginx.conf` with SSL configuration:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name your-domain.com;
       
       ssl_certificate /etc/nginx/ssl/cert.pem;
       ssl_certificate_key /etc/nginx/ssl/key.pem;
       
       # ... rest of configuration
   }
   ```

4. Start the services:
   ```bash
   docker-compose up -d
   ```

5. Access containers at:
   ```
   http://your-domain.com/desktop/{username}-{desktop-type}
   ```

## How the Reverse Proxy Works

### Request Flow

1. **User requests a desktop:**
   ```
   GET http://myserver.com/desktop/alice-ubuntu-vscode
   ```

2. **Nginx (if used) receives the request:**
   - Forwards to Flask app on internal network
   - Maintains WebSocket connection for noVNC

3. **Flask proxy route (`/desktop/<path>`) handles the request:**
   - Extracts proxy path: `alice-ubuntu-vscode`
   - Queries database for matching container
   - Finds container's internal port (e.g., 7001)

4. **Flask proxies the request:**
   ```
   http://localhost:7001 <- proxied from Flask
   ```
   - Forwards all HTTP headers, cookies, and body
   - Streams response back to client
   - Maintains WebSocket connections for noVNC

5. **User sees the Kasm desktop in their browser**

### Database Schema

Each container record includes:
```python
{
    'id': 'uuid',
    'user_id': 'user123',
    'session_id': 'session456',
    'container_name': 'kasm-alice-ubuntu-vscode-abc123',
    'desktop_type': 'ubuntu-vscode',
    'host_port': 7001,           # Internal port
    'proxy_path': 'alice-ubuntu-vscode',  # External path
    'status': 'running'
}
```

## Configuration Details

### Environment Variables

Required in `.env`:
```bash
# Your server's domain (without http:// or port)
DOCKER_HOST_URL=your-domain.com

# Or for local testing
DOCKER_HOST_URL=localhost
```

### Firewall Configuration

#### Option 1: Flask Only
- Open port 5006 (or your Flask port)
- Optional: Use a reverse proxy in front

#### Option 2: With Nginx
- Open port 80 (HTTP)
- Open port 443 (HTTPS) if using SSL
- Block direct access to port 5006 (Flask)
- Block ports 7000-8000 (container ports)

Example firewall rules (ufw):
```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Deny direct container access
sudo ufw deny 7000:8000/tcp

# Allow from localhost only (for Flask)
sudo ufw allow from 127.0.0.1 to any port 5006
```

## Multiple Users / Concurrent Access

The proxy architecture fully supports multiple simultaneous users:

### Scenario
- Alice accesses: `http://myserver.com/desktop/alice-ubuntu-vscode`
- Bob accesses: `http://myserver.com/desktop/bob-ubuntu-desktop`
- Charlie accesses: `http://myserver.com/desktop/charlie-ubuntu-chromium`

### What Happens
1. Each user's container runs on a different port:
   - Alice's container: port 7001
   - Bob's container: port 7002
   - Charlie's container: port 7003

2. Proxy routes map to the correct ports:
   - `/desktop/alice-ubuntu-vscode` → `localhost:7001`
   - `/desktop/bob-ubuntu-desktop` → `localhost:7002`
   - `/desktop/charlie-ubuntu-chromium` → `localhost:7003`

3. All users access via the same HTTP port (80/443) but different paths

## Troubleshooting

### Container not accessible
1. Check container is running:
   ```bash
   docker ps | grep kasm
   ```

2. Check database has proxy_path:
   ```bash
   # Connect to database and query
   SELECT container_name, proxy_path, host_port, status FROM containers;
   ```

3. Check Flask logs for proxy errors:
   ```bash
   docker-compose logs -f app
   ```

### WebSocket connection fails
- **Problem**: noVNC can't connect (black screen, connection error)
- **Solution**: Use nginx reverse proxy (Option 2)
- **Why**: Flask's simple proxy doesn't handle WebSocket upgrades perfectly

### "Container not found" error
1. Ensure container is running and status is 'running'
2. Check proxy_path matches URL:
   - URL: `/desktop/alice-ubuntu-vscode`
   - DB: `proxy_path = 'alice-ubuntu-vscode'`

### Port conflicts
- Shouldn't occur with proxy approach
- Each container still needs a unique internal port (7000-8000)
- External access is through proxy paths, not ports

## Migration from Port-based to Proxy-based

If upgrading from the old port-based system:

1. **Database Migration**:
   The migration script `003_add_proxy_path.sql` automatically adds the `proxy_path` column.

2. **Existing Containers**:
   Existing containers will need to be recreated to get proxy paths:
   ```bash
   # Stop and remove old containers
   docker-compose exec app python3 scripts/cleanup.py
   
   # Or manually via admin panel
   ```

3. **Update URLs**:
   - Old: `http://localhost:7001`
   - New: `http://your-domain.com/desktop/username-desktoptype`

4. **Client Changes**:
   The frontend automatically uses the new URL format returned by the API.

## Security Considerations

### Benefits
- Containers not directly exposed (ports 7000-8000 not accessible)
- Single entry point easier to secure
- Can add authentication at proxy level
- Easier to implement rate limiting
- Better logging and monitoring

### Recommendations
1. Use HTTPS in production (SSL/TLS)
2. Implement rate limiting at nginx level
3. Add authentication middleware to proxy routes
4. Monitor proxy logs for abuse
5. Use firewall rules to block direct container access

## Performance Tuning

### Nginx Configuration
```nginx
# Increase timeouts for long sessions
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;

# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# Buffering
proxy_buffering off;  # For streaming responses
proxy_cache off;      # For dynamic content
```

### Flask Configuration
```python
# In production, use a WSGI server like gunicorn
gunicorn --workers 4 --timeout 3600 --bind 0.0.0.0:5006 run:app
```

## Monitoring

### Key Metrics to Monitor
1. Active proxy connections
2. Proxy response times
3. Container port usage
4. Failed proxy requests
5. WebSocket connection stability

### Logging
Proxy requests are logged in Flask:
```
[INFO] Proxying request to: http://localhost:7001/
[DEBUG] Container alice-ubuntu-vscode accessed by user
```

Check logs:
```bash
docker-compose logs -f app | grep -i proxy
```
