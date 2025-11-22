# Apache Reverse Proxy Setup Guide

This guide explains how to configure Apache as a reverse proxy for the IServ Remote Desktop application running on port 5020.

## Architecture Overview

```
Internet (Port 443) → Apache Reverse Proxy → Flask App (Port 5020) → Docker Containers
```

- **Apache**: Handles SSL termination and WebSocket proxying
- **Flask App**: Runs on port 5020, exposed from Docker container
- **Docker Containers**: Kasm workspaces on ports 7000-8000 (internal only)

## Prerequisites

1. Apache 2.4 or later installed
2. Required Apache modules enabled
3. SSL certificate for your domain

## Step 1: Enable Required Apache Modules

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod proxy_wstunnel
sudo a2enmod rewrite
sudo a2enmod ssl
sudo a2enmod headers
sudo systemctl restart apache2
```

## Step 2: Configure SSL Certificates

### Option A: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-apache

# Generate certificate
sudo certbot --apache -d your-domain.com
```

Certbot will automatically configure Apache and set up auto-renewal.

### Option B: Manual SSL Configuration

If you have your own certificate:

1. Place your certificate files:
   ```bash
   sudo cp your-certificate.crt /etc/ssl/certs/
   sudo cp your-private.key /etc/ssl/private/
   sudo chmod 600 /etc/ssl/private/your-private.key
   ```

2. Update the Apache configuration (see Step 3)

## Step 3: Configure Apache VirtualHost

1. Create Apache configuration file:
   ```bash
   sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf
   ```

2. Copy the content from `apache.conf` in this repository, then update:
   - Replace `your-domain.com` with your actual domain
   - Update SSL certificate paths
   - Verify port 5020 is correct

3. Enable the site:
   ```bash
   sudo a2ensite iserv-remote-desktop.conf
   ```

4. Test configuration:
   ```bash
   sudo apache2ctl configtest
   ```

5. Reload Apache:
   ```bash
   sudo systemctl reload apache2
   ```

## Step 4: Configure Environment Variables

Edit your `.env` file:

```bash
# Use your actual domain
DOCKER_HOST_URL=your-domain.com

# Set protocol to https (Apache handles SSL)
DOCKER_HOST_PROTOCOL=https

# Frontend URL should use https
FRONTEND_URL=https://your-domain.com

# OAuth redirect URI
OAUTH_REDIRECT_URI=https://your-domain.com/authorize
```

## Step 5: Start the Application

```bash
docker-compose up -d
```

The Flask application will be accessible on:
- Internally: `http://localhost:5020`
- Externally: `https://your-domain.com` (via Apache)

## Step 6: Verify Setup

### 1. Check Application is Running

```bash
# Check if Docker container is running
docker-compose ps

# Check if port 5020 is listening
sudo netstat -tlnp | grep 5020
```

You should see:
```
tcp        0      0 0.0.0.0:5020            0.0.0.0:*               LISTEN
```

### 2. Test Internal Connection

```bash
curl http://localhost:5020/health
```

Should return: `healthy` or similar

### 3. Test External HTTPS Connection

```bash
curl https://your-domain.com/health
```

Should return the same response

### 4. Test WebSocket Connection

1. Log in to the application
2. Start a desktop container
3. Open browser developer console
4. Check for WebSocket connection:
   - Look for `wss://your-domain.com/desktop/...` in Network tab
   - Should show "101 Switching Protocols" status
   - Connection should stay open

## Troubleshooting

### Issue: "Connection Aborted" Error

**Symptom**: Error when clicking desktop: `('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))`

**Root Causes**:
1. Container is still starting up and not ready to accept connections
2. Apache timeout settings are too low
3. WebSocket not properly proxied
4. CORS headers interfering with proxy requests

**Solutions**:

1. **Verify Apache Timeout Settings**:
   Your Apache configuration must include proper timeout settings:
   ```apache
   Timeout 3600
   ProxyTimeout 3600
   KeepAlive On
   MaxKeepAliveRequests 100
   KeepAliveTimeout 5
   ```

2. **Check ProxyPass Configuration**:
   Make sure your ProxyPass includes retry parameter:
   ```apache
   ProxyPass / http://localhost:5020/ retry=3 timeout=3600
   ProxyPassReverse / http://localhost:5020/
   ```

3. **Remove Conflicting CORS Headers**:
   If you have CORS headers in your Apache config that restrict origins to specific domains,
   these may interfere with internal proxy requests. Remove or adjust:
   ```apache
   # REMOVE or comment out restrictive CORS headers like:
   # Header always set Access-Control-Allow-Origin "https://specific-domain.com"
   ```

4. **Verify `mod_proxy_wstunnel` is enabled**:
   ```bash
   apache2ctl -M | grep proxy_wstunnel
   ```

5. **Check Apache configuration has WebSocket rewrite rules**:
   ```apache
   RewriteCond %{HTTP:Upgrade} =websocket [NC]
   RewriteRule /(.*)           ws://localhost:5020/$1 [P,L]
   ```

6. **Check Apache error logs**:
   ```bash
   sudo tail -f /var/log/apache2/iserv-remote-desktop-error.log
   ```

7. **Wait for Container Startup**:
   After starting a container, wait 10-15 seconds before accessing it to allow
   the Kasm service to fully initialize. The application now includes automatic
   retry logic, but very slow systems may need additional time.

### Issue: 502 Bad Gateway

**Symptom**: Apache returns 502 error

**Causes & Solutions**:

1. **Flask app not running**:
   ```bash
   docker-compose ps
   docker-compose logs app
   ```

2. **Wrong port**:
   - Verify Flask is on port 5020: `netstat -tlnp | grep 5020`
   - Check docker-compose.yml port mapping: `5020:5006`

3. **SELinux blocking connection** (RHEL/CentOS):
   ```bash
   sudo setsebool -P httpd_can_network_connect 1
   ```

### Issue: WebSocket Connection Failed

**Symptom**: Black screen in noVNC, WebSocket errors in console

**Checklist**:
1. ✓ `mod_proxy_wstunnel` enabled
2. ✓ Rewrite rules in Apache config
3. ✓ DOCKER_HOST_PROTOCOL=https in .env
4. ✓ Access via https://
5. ✓ Check Apache logs for WebSocket upgrade errors

### Issue: "Running container shown as stopped"

**Symptom**: Frontend shows "stopped" for running containers

**Solution**: This was fixed in the latest update. Ensure you're running the latest code:
```bash
git pull
docker-compose down
docker-compose up -d --build
```

## Firewall Configuration

```bash
# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (for redirect to HTTPS)
sudo ufw allow 80/tcp

# Block direct access to Flask (only allow from localhost)
sudo ufw deny from any to any port 5020
sudo ufw allow from 127.0.0.1 to any port 5020

# Block direct container access
sudo ufw deny 7000:8000/tcp
```

## Performance Tuning

### Apache Configuration

Add to your VirtualHost configuration:

```apache
# Increase timeout for long-running connections
Timeout 3600
ProxyTimeout 3600

# Keep-alive settings
KeepAlive On
MaxKeepAliveRequests 100
KeepAliveTimeout 5

# Compression (optional)
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/plain text/xml text/css text/javascript application/javascript application/json
</IfModule>
```

### System Limits

If you expect many concurrent users:

```bash
# Increase Apache connection limits
sudo nano /etc/apache2/mods-available/mpm_event.conf
```

Update:
```apache
<IfModule mpm_event_module>
    StartServers             4
    MinSpareThreads         75
    MaxSpareThreads        250
    ThreadsPerChild         25
    MaxRequestWorkers      400
    MaxConnectionsPerChild   0
</IfModule>
```

## Monitoring

### Check Apache Status

```bash
# Enable status module
sudo a2enmod status

# Add to Apache config
<Location "/server-status">
    SetHandler server-status
    Require local
</Location>
```

Access: `http://localhost/server-status`

### Check Application Logs

```bash
# Apache logs
sudo tail -f /var/log/apache2/iserv-remote-desktop-error.log

# Application logs
docker-compose logs -f app

# Container logs
docker-compose logs -f app | grep -i websocket
```

## Security Best Practices

1. **Use Strong SSL Configuration**:
   - TLS 1.2 or higher only
   - Strong cipher suites
   - Enable HSTS header

2. **Regular Updates**:
   - Keep Apache updated
   - Renew SSL certificates before expiration
   - Update application regularly

3. **Access Control**:
   - Limit access to `/admin` routes
   - Consider IP whitelisting for sensitive endpoints
   - Use fail2ban to prevent brute force attacks

4. **Monitoring**:
   - Set up log monitoring
   - Monitor SSL certificate expiration
   - Track unusual connection patterns

## Alternative: Using Apache with nginx

If you want both Apache (external) and nginx (internal):

1. Apache (Port 443) → nginx (Port 80) → Flask (Port 5020)

This adds complexity but provides additional flexibility. Generally not recommended unless you have specific requirements.

## Testing WebSocket Connection

Create a test HTML file:

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
</head>
<body>
    <h1>WebSocket Connection Test</h1>
    <div id="status"></div>
    <script>
        const ws = new WebSocket('wss://your-domain.com/desktop/test');
        const status = document.getElementById('status');
        
        ws.onopen = () => {
            status.textContent = '✓ WebSocket connected successfully!';
            status.style.color = 'green';
        };
        
        ws.onerror = (error) => {
            status.textContent = '✗ WebSocket connection failed';
            status.style.color = 'red';
            console.error(error);
        };
    </script>
</body>
</html>
```

## Additional Resources

- [Apache mod_proxy_wstunnel Documentation](https://httpd.apache.org/docs/2.4/mod/mod_proxy_wstunnel.html)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Apache SSL Configuration](https://httpd.apache.org/docs/2.4/ssl/)

## Support

For issues related to Apache configuration:
1. Check Apache logs: `sudo tail -f /var/log/apache2/error.log`
2. Check application logs: `docker-compose logs app`
3. Verify configuration: `sudo apache2ctl configtest`
4. Test connectivity: `curl -v http://localhost:5020/health`
