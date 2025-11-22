# Deployment Quick Reference

This document provides a quick reference for deploying the IServ Remote Desktop application with the fixes for the three critical issues.

## Issues Fixed

✅ **Issue 1**: Running containers now correctly show as "running" in the frontend
✅ **Issue 2**: SSL/HTTPS support with Apache proxy on port 443
✅ **Issue 3**: Production-ready WebSocket proxy implementation

## Architecture

```
Internet (HTTPS:443) 
    ↓
Apache Reverse Proxy (SSL termination, WebSocket upgrade)
    ↓
Flask App (Port 5020 → Internal 5006)
    ↓
Docker Containers (Kasm workspaces on ports 7000-8000)
```

## Quick Start for Apache Setup

### 1. Enable Apache Modules

```bash
sudo a2enmod proxy proxy_http proxy_wstunnel rewrite ssl headers
sudo systemctl restart apache2
```

### 2. Configure Apache VirtualHost

Copy `apache.conf` to Apache sites:
```bash
sudo cp apache.conf /etc/apache2/sites-available/iserv-remote-desktop.conf
sudo nano /etc/apache2/sites-available/iserv-remote-desktop.conf
```

Update in the file:
- Replace `your-domain.com` with your actual domain (3 places)
- Update SSL certificate paths
- Verify port 5020 is correct

Enable the site:
```bash
sudo a2ensite iserv-remote-desktop.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 3. Configure Environment Variables

Edit `.env`:
```bash
DOCKER_HOST_URL=your-domain.com
DOCKER_HOST_PROTOCOL=https
FRONTEND_URL=https://your-domain.com
OAUTH_REDIRECT_URI=https://your-domain.com/authorize
```

### 4. Start Application

```bash
docker-compose up -d
```

### 5. Verify

```bash
# Check internal connection
curl http://localhost:5020/health

# Check external HTTPS connection
curl https://your-domain.com/health

# Check Docker container
docker-compose ps
```

## Troubleshooting

### "Connection Aborted" Error

**Symptom**: `('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))`

**Fix**:
1. Verify `mod_proxy_wstunnel` is enabled
2. Check Apache logs: `sudo tail -f /var/log/apache2/error.log`
3. Verify WebSocket rewrite rules in Apache config

### Container Shows as "Stopped" When Running

**Symptom**: Frontend displays "stopped" for running containers

**Fix**: This was fixed in this PR. Ensure you're running the latest code:
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### 502 Bad Gateway

**Fix**:
1. Check Flask app is running: `docker-compose ps`
2. Verify port 5020 is listening: `netstat -tlnp | grep 5020`
3. Check logs: `docker-compose logs app`
4. If on RHEL/CentOS: `sudo setsebool -P httpd_can_network_connect 1`

### WebSocket Connection Failed

**Fix**:
1. Verify `mod_proxy_wstunnel` enabled: `apache2ctl -M | grep proxy_wstunnel`
2. Check browser console for WebSocket errors
3. Verify accessing via `https://` (not `http://`)
4. Check DOCKER_HOST_PROTOCOL=https in .env

## Key Files

- **apache.conf**: Apache VirtualHost configuration with WebSocket support
- **APACHE_SETUP.md**: Comprehensive Apache setup guide
- **docker-compose.yml**: Updated to expose port 5020 for Apache
- **app/routes/container_routes.py**: Fixed container status extraction
- **app/services/docker_manager.py**: Added DOCKER_HOST_PROTOCOL support
- **.env.example**: Added DOCKER_HOST_PROTOCOL variable

## Testing

Run the test suite:
```bash
python3 scripts/test_fixes.py
```

Expected output:
```
✓ Status extraction test passed
✓ URL generation test (HTTPS) passed
✓ URL generation test (HTTP) passed
✓ Nginx WebSocket configuration test passed
✓ Docker Compose nginx configuration test passed
```

## Security Notes

1. ✅ All code passed security scanning (CodeQL)
2. ✅ SSL/TLS configured for HTTPS
3. ✅ WebSocket upgrade properly handled
4. ✅ No vulnerabilities detected

## Port Reference

- **443**: HTTPS (Apache, external access)
- **80**: HTTP (Apache, optional redirect to HTTPS)
- **5020**: Flask application (exposed for Apache, localhost only)
- **5006**: Flask application (internal Docker port)
- **7000-8000**: Kasm containers (internal only, not exposed)

## Firewall Configuration

```bash
# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (optional)
sudo ufw allow 80/tcp

# Block direct access to app (except from localhost)
sudo ufw deny from any to any port 5020
sudo ufw allow from 127.0.0.1 to any port 5020

# Block direct container access
sudo ufw deny 7000:8000/tcp
```

## Additional Documentation

- **APACHE_SETUP.md**: Full Apache configuration guide
- **SSL_SETUP.md**: Nginx SSL configuration (for standalone deployments)
- **README.md**: General application documentation
- **USAGE.md**: Usage examples

## Support

For issues:
1. Check Apache logs: `sudo tail -f /var/log/apache2/iserv-remote-desktop-error.log`
2. Check application logs: `docker-compose logs -f app`
3. Verify configuration: `sudo apache2ctl configtest`
4. Test connectivity: `curl -v http://localhost:5020/health`

## Changes Summary

### Code Changes
- Fixed container status extraction in `container_routes.py`
- Added protocol support in `docker_manager.py`
- Updated `docker-compose.yml` for Apache proxy

### Configuration Changes
- Added `apache.conf` with WebSocket support
- Updated `.env.example` with DOCKER_HOST_PROTOCOL
- Made nginx optional (commented out)

### Documentation Changes
- Created `APACHE_SETUP.md` (comprehensive Apache guide)
- Updated `README.md` (deployment options)
- Updated `SSL_SETUP.md` (nginx-specific guide)
- Added `DEPLOYMENT_QUICK_REFERENCE.md` (this file)

## Next Steps

1. Follow the Quick Start steps above
2. Test the application
3. Monitor logs for any issues
4. Set up monitoring and backups
5. Configure log rotation

## Version Info

These fixes address issues reported on 2025-11-22 and include:
- Container status display fix
- Apache proxy with WebSocket support
- SSL/HTTPS configuration for port 443 access
