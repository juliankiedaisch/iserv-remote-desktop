# SSL/HTTPS Setup Guide (Nginx)

**Note**: This guide is for standalone deployments using the internal nginx reverse proxy. If you're using an external Apache proxy, see [APACHE_SETUP.md](APACHE_SETUP.md) instead.

This guide explains how to configure SSL/HTTPS with nginx for the remote desktop application to ensure secure WebSocket connections.

## Why SSL/HTTPS is Important

1. **Security**: Encrypts all traffic between clients and the server
2. **WebSocket Support**: Modern browsers require secure WebSocket connections (wss://) for proper noVNC functionality
3. **Port 443 Access**: When only HTTPS port 443 is accessible from the internet, SSL is required

## Quick Start (Development)

For development and testing, generate self-signed certificates:

```bash
./scripts/generate_ssl_cert.sh
```

This creates:
- `ssl/cert.pem` - SSL certificate
- `ssl/key.pem` - Private key

**Warning**: Self-signed certificates will show browser warnings. Only use for development.

## Production Setup Options

### Option 1: Let's Encrypt (Recommended)

Let's Encrypt provides free, automated SSL certificates.

#### Using Certbot

1. Install Certbot:
   ```bash
   sudo apt-get update
   sudo apt-get install certbot
   ```

2. Stop nginx if running:
   ```bash
   docker-compose down
   ```

3. Generate certificates:
   ```bash
   sudo certbot certonly --standalone -d your-domain.com
   ```

4. Copy certificates to the ssl directory:
   ```bash
   sudo mkdir -p ssl
   sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
   sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
   sudo chown $USER:$USER ssl/*.pem
   ```

5. Set up auto-renewal:
   ```bash
   sudo crontab -e
   ```
   
   Add this line to renew certificates monthly:
   ```
   0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /path/to/app/ssl/cert.pem && cp /etc/letsencrypt/live/your-domain.com/privkey.pem /path/to/app/ssl/key.pem && docker-compose restart nginx
   ```

#### Using Docker with Let's Encrypt

Alternatively, use a Docker-based Let's Encrypt solution:

1. Update `docker-compose.yml` to include certbot:
   ```yaml
   certbot:
     image: certbot/certbot
     volumes:
       - ./certbot/conf:/etc/letsencrypt
       - ./certbot/www:/var/www/certbot
     entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
   ```

2. Add volume for certbot to nginx:
   ```yaml
   nginx:
     volumes:
       - ./certbot/conf:/etc/letsencrypt
       - ./certbot/www:/var/www/certbot
   ```

3. Update nginx.conf to handle Let's Encrypt validation:
   ```nginx
   location /.well-known/acme-challenge/ {
       root /var/www/certbot;
   }
   ```

### Option 2: Commercial Certificate

If you have a commercial SSL certificate:

1. Place your certificate and key in the `ssl` directory:
   ```bash
   mkdir -p ssl
   cp your-certificate.crt ssl/cert.pem
   cp your-private-key.key ssl/key.pem
   chmod 600 ssl/key.pem
   chmod 644 ssl/cert.pem
   ```

2. If you have intermediate certificates, concatenate them:
   ```bash
   cat your-certificate.crt intermediate.crt > ssl/cert.pem
   ```

## Configuration

### 1. Update Environment Variables

Edit your `.env` file:

```bash
# Use your actual domain
DOCKER_HOST_URL=your-domain.com

# Set protocol to https
DOCKER_HOST_PROTOCOL=https

# Frontend URL should also use https
FRONTEND_URL=https://your-domain.com

# OAuth redirect URI should use https
OAUTH_REDIRECT_URI=https://your-domain.com/authorize
```

### 2. Verify Nginx Configuration

The `nginx.conf` file is already configured for SSL. It listens on both:
- Port 80 (HTTP) - for redirects or non-SSL access
- Port 443 (HTTPS) - for secure connections

Key SSL settings in `nginx.conf`:
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
}
```

### 3. Start the Application

```bash
docker-compose up -d
```

## Testing SSL Setup

### 1. Test HTTPS Access

```bash
curl -k https://your-domain.com/health
```

You should see: `healthy`

### 2. Test WebSocket Connection

1. Log in to the application
2. Start a desktop container
3. Check browser console for WebSocket connection:
   - Should show `wss://` (secure WebSocket) protocol
   - No connection errors

### 3. Verify SSL Certificate

```bash
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

Check the certificate details and expiration date.

## Troubleshooting

### "Connection Aborted" Error

**Symptom**: Error connecting to container: `('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))`

**Cause**: WebSocket connection not properly proxied

**Solution**:
1. Ensure nginx is running: `docker-compose ps`
2. Check nginx logs: `docker-compose logs nginx`
3. Verify WebSocket headers in nginx.conf
4. Confirm DOCKER_HOST_PROTOCOL=https in .env

### Self-Signed Certificate Warning

**Symptom**: Browser shows "Your connection is not private"

**Solution**: 
- For development: Click "Advanced" → "Proceed anyway"
- For production: Use Let's Encrypt or commercial certificate

### WebSocket Connection Failed

**Symptom**: Black screen in noVNC, WebSocket connection error in console

**Checklist**:
1. ✓ Nginx is running
2. ✓ SSL certificates are valid and mounted
3. ✓ DOCKER_HOST_PROTOCOL=https in .env
4. ✓ Browser is accessing via https://
5. ✓ Firewall allows port 443

### Certificate Not Found

**Symptom**: nginx fails to start with "certificate file not found"

**Solution**:
1. Verify ssl directory exists: `ls -la ssl/`
2. Check certificate files: `ls -la ssl/*.pem`
3. Generate certificates if missing: `./scripts/generate_ssl_cert.sh`
4. Verify docker-compose.yml mounts ssl directory

## Firewall Configuration

For production deployments with SSL:

```bash
# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (optional, for redirects)
sudo ufw allow 80/tcp

# Block direct access to Flask app
sudo ufw deny 5006/tcp

# Block direct container access
sudo ufw deny 7000:8000/tcp
```

## Security Best Practices

1. **Never commit certificates**: The `.gitignore` file already excludes the `ssl/` directory
2. **Use strong passwords**: Set a strong VNC_PASSWORD in .env
3. **Regular updates**: Keep SSL certificates up to date
4. **Monitor expiration**: Set up alerts for certificate expiration
5. **Use HSTS**: Consider adding HTTP Strict Transport Security headers
6. **Regular backups**: Back up your SSL certificates securely

## Additional Resources

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [WebSocket over SSL](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

## Support

If you encounter issues with SSL setup:

1. Check nginx logs: `docker-compose logs nginx`
2. Check Flask logs: `docker-compose logs app`
3. Verify environment variables: `docker-compose config`
4. Test container connectivity: `docker exec -it <container-id> curl localhost:6901`
