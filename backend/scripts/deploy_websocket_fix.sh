#!/bin/bash
# Quick deployment script for WebSocket Apache fix
# Run this on your Apache proxy server (NOT the Docker host)

set -e

echo "=================================================="
echo "WebSocket Apache Configuration Fix Deployment"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration file location (adjust if needed)
APACHE_CONFIG="/etc/apache2/sites-available/desktop.conf"
APACHE_CONFIG_ENABLED="/etc/apache2/sites-enabled/desktop.conf"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

echo "Step 1: Backing up current configuration..."
if [ -f "$APACHE_CONFIG" ]; then
    cp "$APACHE_CONFIG" "${APACHE_CONFIG}.backup-$(date +%Y%m%d-%H%M%S)"
    echo -e "${GREEN}✓ Backup created${NC}"
else
    echo -e "${YELLOW}⚠ Configuration file not found at $APACHE_CONFIG${NC}"
    echo "Please specify the correct path in this script"
    exit 1
fi

echo ""
echo "Step 2: Checking required Apache modules..."
REQUIRED_MODULES="proxy proxy_http proxy_wstunnel rewrite ssl headers"
MISSING_MODULES=""

for module in $REQUIRED_MODULES; do
    if ! apache2ctl -M 2>/dev/null | grep -q "${module}_module"; then
        MISSING_MODULES="$MISSING_MODULES $module"
        echo -e "${YELLOW}⚠ Module $module is not enabled${NC}"
    else
        echo -e "${GREEN}✓ Module $module is enabled${NC}"
    fi
done

if [ -n "$MISSING_MODULES" ]; then
    echo ""
    echo -e "${YELLOW}Enabling missing modules:${MISSING_MODULES}${NC}"
    for module in $MISSING_MODULES; do
        a2enmod $module
    done
    echo -e "${GREEN}✓ Modules enabled${NC}"
fi

echo ""
echo "Step 3: You need to manually update the configuration file"
echo -e "${YELLOW}→ Edit: $APACHE_CONFIG${NC}"
echo ""
echo "Add these lines after the KeepAlive settings:"
echo "----------------------------------------"
cat << 'EOF'
    # WebSocket support - CRITICAL for noVNC
    # Using ProxyPass with upgrade=websocket to handle both HTTP and WebSocket traffic
    # This is the recommended approach for Apache 2.4.47+ with mod_proxy_wstunnel
    
    # Enable RewriteEngine for WebSocket handling
    RewriteEngine On
    
    # WebSocket-specific proxying for /websockify endpoint
    # When Upgrade header is present, handle as WebSocket
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/(.*) ws://172.22.0.27:5020/$1 [P,L]
    
    # Regular HTTP proxying for all other requests
    # Frontend application
    ProxyPass / http://172.22.0.27:5020/ retry=3 timeout=3600
    ProxyPassReverse / http://172.22.0.27:5020/
EOF
echo "----------------------------------------"
echo ""
echo "Remove these lines if present:"
echo "  - SetEnvIf directives"
echo "  - RequestHeader set Upgrade/Connection with env= conditions"
echo ""

read -p "Press Enter after you've updated the configuration file..."

echo ""
echo "Step 4: Testing configuration..."
if apache2ctl configtest; then
    echo -e "${GREEN}✓ Configuration syntax is OK${NC}"
else
    echo -e "${RED}✗ Configuration has syntax errors${NC}"
    echo "Please fix the errors before continuing"
    exit 1
fi

echo ""
echo "Step 5: Reloading Apache..."
if systemctl reload apache2; then
    echo -e "${GREEN}✓ Apache reloaded successfully${NC}"
else
    echo -e "${RED}✗ Apache reload failed${NC}"
    echo "Attempting restart..."
    if systemctl restart apache2; then
        echo -e "${GREEN}✓ Apache restarted successfully${NC}"
    else
        echo -e "${RED}✗ Apache restart failed${NC}"
        echo "Please check the logs: journalctl -xe"
        exit 1
    fi
fi

echo ""
echo "=================================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Monitor Apache logs:"
echo "   tail -f /var/log/apache2/desktop_error.log"
echo ""
echo "2. Test WebSocket connection:"
echo "   - Open https://desktop.hub.mdg-hamburg.de"
echo "   - Start a container"
echo "   - Check browser console (F12) for WebSocket errors"
echo ""
echo "3. If issues persist, check:"
echo "   - Flask is running on 172.22.0.27:5020"
echo "   - Firewall allows connections between servers"
echo "   - Apache error logs for details"
echo ""
