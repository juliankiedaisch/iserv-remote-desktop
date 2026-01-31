#!/bin/bash
#
# Coturn TURN/STUN Server Installation Script
# For iserv-remote-desktop WebRTC support
#
# Usage: sudo ./install_coturn.sh [DOMAIN] [PUBLIC_IP]
# Example: sudo ./install_coturn.sh turn.hub.mdg-hamburg.de 203.0.113.45
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo $0 [DOMAIN] [PUBLIC_IP]"
    exit 1
fi

# Get parameters or prompt
DOMAIN=${1:-"turn.example.com"}
PUBLIC_IP=${2:-""}

if [ -z "$PUBLIC_IP" ]; then
    # Try to detect public IP
    PUBLIC_IP=$(curl -s https://api.ipify.org)
    if [ -z "$PUBLIC_IP" ]; then
        echo -e "${RED}Error: Could not detect public IP address${NC}"
        echo "Please provide it manually: sudo $0 $DOMAIN YOUR_PUBLIC_IP"
        exit 1
    fi
    echo -e "${YELLOW}Detected public IP: $PUBLIC_IP${NC}"
    read -p "Is this correct? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your public IP address: " PUBLIC_IP
    fi
fi

# Generate random passwords
TURN_USER="kasmuser"
TURN_PASSWORD=$(openssl rand -base64 24)
STATIC_AUTH_SECRET=$(openssl rand -base64 32)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Coturn Installation for iserv-remote-desktop${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Domain: $DOMAIN"
echo "Public IP: $PUBLIC_IP"
echo "TURN Username: $TURN_USER"
echo ""

# Update system
echo -e "${GREEN}[1/6] Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

# Install coturn
echo -e "${GREEN}[2/6] Installing coturn...${NC}"
apt-get install -y coturn

# Enable coturn
echo -e "${GREEN}[3/6] Enabling coturn service...${NC}"
sed -i 's/#TURNSERVER_ENABLED=1/TURNSERVER_ENABLED=1/' /etc/default/coturn

# Backup original config
if [ -f /etc/turnserver.conf ]; then
    cp /etc/turnserver.conf /etc/turnserver.conf.backup.$(date +%Y%m%d_%H%M%S)
fi

# Create configuration
echo -e "${GREEN}[4/6] Creating coturn configuration...${NC}"
cat > /etc/turnserver.conf << EOF
# TURN server name and realm
realm=$DOMAIN
server-name=$DOMAIN

# Use fingerprints in the TURN messages
fingerprint

# IPs the TURN server listens to
listening-ip=0.0.0.0
listening-port=3478

# External IP address
external-ip=$PUBLIC_IP

# Relay IP address
relay-ip=$PUBLIC_IP

# Port range for relay connections
min-port=49152
max-port=65535

# Log file location
log-file=/var/log/turnserver/turnserver.log
simple-log

# Use long-term credentials mechanism
lt-cred-mech

# User accounts for TURN server authentication
user=$TURN_USER:$TURN_PASSWORD

# Disable CLI
no-cli

# Mobility with ICE
mobility

# Ban private IP ranges from being used as relay addresses
no-loopback-peers
no-multicast-peers

# Use auth secret for REST API
use-auth-secret
static-auth-secret=$STATIC_AUTH_SECRET

# Additional security settings
stale-nonce=600
max-bps=1000000

# Disable UDP relay to force TCP/TLS (optional)
# Uncomment if you want to use only TCP
# no-udp-relay

# TLS configuration (optional - requires SSL certificates)
# Uncomment and configure after obtaining SSL certificates
# tls-listening-port=5349
# cert=/etc/ssl/certs/turn_server_cert.pem
# pkey=/etc/ssl/private/turn_server_pkey.pem
EOF

# Create log directory
mkdir -p /var/log/turnserver
chown turnserver:turnserver /var/log/turnserver

# Configure firewall (if ufw is active)
echo -e "${GREEN}[5/6] Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    if ufw status | grep -q "Status: active"; then
        echo "UFW is active, opening ports..."
        ufw allow 3478/tcp
        ufw allow 3478/udp
        ufw allow 5349/tcp
        ufw allow 5349/udp
        ufw allow 49152:65535/tcp
        ufw allow 49152:65535/udp
        ufw reload
        echo "Firewall rules added"
    else
        echo "UFW is not active, skipping firewall configuration"
    fi
else
    echo "UFW not found, skipping firewall configuration"
fi

# Start coturn
echo -e "${GREEN}[6/6] Starting coturn service...${NC}"
systemctl enable coturn
systemctl restart coturn

# Wait for service to start
sleep 2

# Check status
if systemctl is-active --quiet coturn; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Coturn installation completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Warning: Coturn service may not have started correctly${NC}"
    echo -e "${RED}========================================${NC}"
    systemctl status coturn --no-pager
fi

# Create credentials file
CREDS_FILE="/root/coturn_credentials.txt"
cat > $CREDS_FILE << EOF
========================================
Coturn TURN/STUN Server Credentials
========================================

Domain: $DOMAIN
Public IP: $PUBLIC_IP

TURN Server URL: turn:$DOMAIN:3478
STUN Server URL: stun:$DOMAIN:3478

Authentication:
  Username: $TURN_USER
  Password: $TURN_PASSWORD
  
REST API Secret:
  Static Auth Secret: $STATIC_AUTH_SECRET

Firewall Ports:
  STUN/TURN: 3478 (TCP/UDP)
  TURN TLS: 5349 (TCP/UDP)
  Relay Range: 49152-65535 (TCP/UDP)

Configuration File: /etc/turnserver.conf
Log File: /var/log/turnserver/turnserver.log

========================================
Backend .env Configuration
========================================

Add these to your backend/.env file:

TURN_SERVER_URL=turn:$DOMAIN:3478
TURN_SERVER_USERNAME=$TURN_USER
TURN_SERVER_CREDENTIAL=$TURN_PASSWORD
TURN_STATIC_AUTH_SECRET=$STATIC_AUTH_SECRET
STUN_SERVER_URL=stun:$DOMAIN:3478
WEBRTC_ENABLED=true
LOCAL_NETWORK_CIDR=192.168.0.0/16,10.0.0.0/8,172.16.0.0/12

========================================
Frontend .env Configuration
========================================

Add these to your frontend/.env file:

REACT_APP_WEBRTC_ENABLED=true
REACT_APP_TURN_SERVER_URL=turn:$DOMAIN:3478
REACT_APP_STUN_SERVER_URL=stun:$DOMAIN:3478

========================================
Next Steps
========================================

1. Review the configuration:
   sudo nano /etc/turnserver.conf

2. Check service status:
   sudo systemctl status coturn

3. View logs:
   sudo tail -f /var/log/turnserver/turnserver.log

4. Test STUN functionality:
   stunclient $DOMAIN

5. (Optional) Set up SSL/TLS certificates:
   - Install certbot: sudo apt-get install certbot
   - Get certificate: sudo certbot certonly --standalone -d $DOMAIN
   - Update /etc/turnserver.conf with certificate paths
   - Restart coturn: sudo systemctl restart coturn

6. Configure backend and frontend .env files with the credentials above

7. For security, store credentials securely and delete this file:
   sudo shred -u $CREDS_FILE

========================================
EOF

chmod 600 $CREDS_FILE

echo ""
echo -e "${GREEN}Credentials saved to: $CREDS_FILE${NC}"
echo -e "${YELLOW}IMPORTANT: Store these credentials securely!${NC}"
echo ""
cat $CREDS_FILE
echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Service status:"
systemctl status coturn --no-pager | head -5
echo ""
echo "For detailed setup instructions, see COTURN_SETUP.md"
