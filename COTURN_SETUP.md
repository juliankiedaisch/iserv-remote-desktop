# Coturn TURN/STUN Server Setup for iserv-remote-desktop

This document describes how to install and configure a coturn TURN/STUN server to enable direct WebRTC connections for audio and video streaming in the iserv-remote-desktop application.

## Overview

The coturn server acts as a TURN/STUN relay server that enables WebRTC connections between clients and containers. This allows:

1. **Local Network**: Direct UDP connections from client to container (bypassing Apache proxy)
2. **External Network**: TURN relay through coturn server when direct connection is not possible
3. **Security**: Maintains security by requiring authentication and using the TURN server for external access

## Benefits

- **Reduced Latency**: Direct UDP connections have lower latency than WebSocket over TCP
- **Better Performance**: UDP is more efficient for real-time audio/video streaming
- **Reduced Server Load**: Direct connections don't route through Apache, reducing proxy overhead
- **Scalability**: Can handle many more concurrent connections

## Prerequisites

- Ubuntu/Debian server with root access
- Public IP address for the coturn server
- Firewall configuration capability
- SSL certificates (optional but recommended)

## Installation

### 1. Install Coturn

```bash
# Update package list
sudo apt-get update

# Install coturn
sudo apt-get install -y coturn

# Enable coturn service
sudo sed -i 's/#TURNSERVER_ENABLED=1/TURNSERVER_ENABLED=1/' /etc/default/coturn
```

### 2. Configure Coturn

Create or edit `/etc/turnserver.conf`:

```bash
sudo nano /etc/turnserver.conf
```

Use the following configuration (adjust values as needed):

```conf
# TURN server name and realm
realm=turn.hub.mdg-hamburg.de
server-name=turn.hub.mdg-hamburg.de

# Use fingerprints in the TURN messages
fingerprint

# IPs the TURN server listens to
listening-ip=0.0.0.0
listening-port=3478

# External IP address (your server's public IP)
# Replace with your actual public IP
external-ip=YOUR_PUBLIC_IP

# Relay IP address
relay-ip=YOUR_PUBLIC_IP

# Port range for relay connections
min-port=49152
max-port=65535

# Enable verbose logging (for debugging, disable in production)
verbose

# Log file location
log-file=/var/log/turnserver.log

# Use long-term credentials mechanism
lt-cred-mech

# User accounts for TURN server authentication
# Format: username:password
# Generate strong passwords and replace these
user=kasmuser:CHANGE_THIS_PASSWORD
user=turnuser:CHANGE_THIS_PASSWORD

# Disable UDP relay endpoints (use only TCP or TLS)
# Comment these lines if you want to allow UDP relay
# no-udp-relay
# no-udp

# Enable TLS/DTLS (recommended for production)
# Uncomment and configure if you have SSL certificates
# tls-listening-port=5349
# cert=/etc/ssl/certs/turn_server_cert.pem
# pkey=/etc/ssl/private/turn_server_pkey.pem

# Disable CLI
no-cli

# SQLite database for long-term credentials (optional)
# userdb=/var/lib/turn/turndb

# Mobility with ICE
mobility

# Ban private IP ranges from being used as relay addresses
no-loopback-peers
no-multicast-peers

# Allow TURN REST API
use-auth-secret
static-auth-secret=CHANGE_THIS_SECRET_KEY

# Additional security settings
stale-nonce=600
max-bps=1000000
bps-capacity=0
```

### 3. Configure Firewall

Open the necessary ports for coturn:

```bash
# STUN/TURN TCP and UDP
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp

# TURN TLS (if using TLS)
sudo ufw allow 5349/tcp
sudo ufw allow 5349/udp

# Relay ports range
sudo ufw allow 49152:65535/tcp
sudo ufw allow 49152:65535/udp

# Reload firewall
sudo ufw reload
```

### 4. Configure SSL/TLS (Recommended)

If you want to use secure connections (highly recommended for production):

```bash
# Using Let's Encrypt
sudo apt-get install -y certbot

# Obtain certificates
sudo certbot certonly --standalone -d turn.hub.mdg-hamburg.de

# Link certificates to coturn config locations
sudo ln -s /etc/letsencrypt/live/turn.hub.mdg-hamburg.de/fullchain.pem /etc/ssl/certs/turn_server_cert.pem
sudo ln -s /etc/letsencrypt/live/turn.hub.mdg-hamburg.de/privkey.pem /etc/ssl/private/turn_server_pkey.pem

# Set permissions
sudo chown turnserver:turnserver /etc/ssl/certs/turn_server_cert.pem
sudo chown turnserver:turnserver /etc/ssl/private/turn_server_pkey.pem
```

Then uncomment the TLS lines in `/etc/turnserver.conf`:

```conf
tls-listening-port=5349
cert=/etc/ssl/certs/turn_server_cert.pem
pkey=/etc/ssl/private/turn_server_pkey.pem
```

### 5. Start Coturn Service

```bash
# Start coturn
sudo systemctl start coturn

# Enable coturn to start on boot
sudo systemctl enable coturn

# Check status
sudo systemctl status coturn

# View logs
sudo tail -f /var/log/turnserver.log
```

## Configuration for iserv-remote-desktop

### Backend Configuration

Add the following to your backend `.env` file:

```bash
# TURN/STUN Server Configuration
TURN_SERVER_URL=turn:turn.hub.mdg-hamburg.de:3478
TURN_SERVER_USERNAME=kasmuser
TURN_SERVER_CREDENTIAL=CHANGE_THIS_PASSWORD

# Or use static auth secret (REST API method)
TURN_STATIC_AUTH_SECRET=CHANGE_THIS_SECRET_KEY

# STUN Server (can be same as TURN)
STUN_SERVER_URL=stun:turn.hub.mdg-hamburg.de:3478

# Enable WebRTC for direct connections
WEBRTC_ENABLED=true

# Local network detection (optional)
# Define local network CIDR ranges for direct connection detection
LOCAL_NETWORK_CIDR=192.168.0.0/16,10.0.0.0/8,172.16.0.0/12
```

### Frontend Configuration

Add to `frontend/.env`:

```bash
REACT_APP_WEBRTC_ENABLED=true
REACT_APP_TURN_SERVER_URL=turn:turn.hub.mdg-hamburg.de:3478
REACT_APP_STUN_SERVER_URL=stun:turn.hub.mdg-hamburg.de:3478
```

## Testing the TURN Server

### Test with Trickle ICE

Visit https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/

1. Add your TURN server URL: `turn:turn.hub.mdg-hamburg.de:3478`
2. Add username and credential from your configuration
3. Click "Gather candidates"
4. You should see relay candidates with type "relay"

### Test with Command Line

```bash
# Install TURN client
sudo apt-get install -y libnice-bin

# Test STUN
stunclient turn.hub.mdg-hamburg.de

# Test TURN with credentials
turnutils_uclient -v -u kasmuser -w CHANGE_THIS_PASSWORD turn.hub.mdg-hamburg.de
```

## Monitoring and Troubleshooting

### Check Logs

```bash
# View coturn logs
sudo tail -f /var/log/turnserver.log

# Check for errors
sudo journalctl -u coturn -f
```

### Common Issues

1. **Connection refused**: Check firewall rules and ensure ports are open
2. **Authentication failed**: Verify username/password in configuration
3. **No relay candidates**: Check external-ip setting matches your public IP
4. **TLS errors**: Verify certificate paths and permissions

### Performance Monitoring

```bash
# Check active connections
sudo netstat -anp | grep turnserver

# Monitor resource usage
sudo htop -p $(pgrep turnserver)
```

## Apache Integration

If coturn is running on the same server as Apache, you may want to add a monitoring endpoint:

Add to your Apache configuration:

```apache
# Coturn stats endpoint (admin only)
<Location /turn-stats>
    ProxyPass http://localhost:8080/stats
    ProxyPassReverse http://localhost:8080/stats
    Require ip YOUR_ADMIN_IP
</Location>
```

## Security Considerations

1. **Strong Passwords**: Use strong, unique passwords for TURN authentication
2. **Rate Limiting**: Consider implementing rate limiting to prevent abuse
3. **Monitoring**: Monitor logs for suspicious activity
4. **Updates**: Keep coturn updated with security patches
5. **Firewall**: Restrict access to only necessary ports
6. **TLS**: Always use TLS/DTLS in production environments

## Production Deployment Checklist

- [ ] Install coturn
- [ ] Configure realm and server name
- [ ] Set external IP address
- [ ] Configure strong authentication credentials
- [ ] Enable TLS/DTLS with valid certificates
- [ ] Open firewall ports
- [ ] Test STUN/TURN functionality
- [ ] Configure backend .env with TURN settings
- [ ] Configure frontend .env with TURN settings
- [ ] Monitor logs for errors
- [ ] Set up log rotation for /var/log/turnserver.log
- [ ] Document credentials securely
- [ ] Set up monitoring and alerts

## Further Reading

- [Coturn Documentation](https://github.com/coturn/coturn/wiki)
- [WebRTC TURN/STUN Guide](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols)
- [RFC 5766 - TURN](https://tools.ietf.org/html/rfc5766)
- [RFC 5389 - STUN](https://tools.ietf.org/html/rfc5389)
