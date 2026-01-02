#!/bin/bash
# Configure firewall and Apache for direct container port access
#
# This script must be run on the Apache server (172.22.0.10)
# It opens firewall ports and optionally configures Apache SSL for those ports

set -e

echo "=========================================="
echo "KasmVNC Direct Port Access Setup"
echo "=========================================="
echo
echo "This will configure access to KasmVNC containers via direct port mapping."
echo "Containers will be accessible at: https://desktop.hub.mdg-hamburg.de:7000-7100/"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root"
    exit 1
fi

# Detect firewall system
if command -v ufw &> /dev/null; then
    FIREWALL="ufw"
elif command -v firewall-cmd &> /dev/null; then
    FIREWALL="firewalld"
elif command -v iptables &> /dev/null; then
    FIREWALL="iptables"
else
    echo "ERROR: No supported firewall found (ufw, firewalld, or iptables)"
    exit 1
fi

echo "Detected firewall: $FIREWALL"
echo

# Open ports 7000-7100
echo "Opening TCP ports 7000-7100..."

case $FIREWALL in
    ufw)
        for port in {7000..7100}; do
            ufw allow $port/tcp comment "KasmVNC container port"
        done
        ufw reload
        echo "✓ UFW rules added"
        ;;
    
    firewalld)
        for port in {7000..7100}; do
            firewall-cmd --permanent --add-port=$port/tcp
        done
        firewall-cmd --reload
        echo "✓ Firewalld rules added"
        ;;
    
    iptables)
        # Add rule if it doesn't exist
        if ! iptables -C INPUT -p tcp --dport 7000:7100 -j ACCEPT 2>/dev/null; then
            iptables -A INPUT -p tcp --dport 7000:7100 -j ACCEPT
            
            # Save rules
            if [ -d /etc/iptables ]; then
                iptables-save > /etc/iptables/rules.v4
            elif [ -f /etc/sysconfig/iptables ]; then
                iptables-save > /etc/sysconfig/iptables
            else
                echo "WARNING: Could not find iptables save location. Rules will be lost on reboot."
                echo "Run 'iptables-save > /etc/iptables/rules.v4' manually."
            fi
        fi
        echo "✓ iptables rules added"
        ;;
esac

echo
echo "=========================================="
echo "Firewall Configuration Complete"
echo "=========================================="
echo
echo "Ports 7000-7100 are now open for KasmVNC container access."
echo
echo "Next steps:"
echo "1. Test port access from Flask server:"
echo "   curl -k -I https://172.22.0.27:7000/"
echo
echo "2. Test from external domain:"
echo "   curl -k -I https://desktop.hub.mdg-hamburg.de:7000/"
echo
echo "3. Open in browser:"
echo "   https://desktop.hub.mdg-hamburg.de:7000/"
echo
echo "4. Access via web interface:"
echo "   https://desktop.hub.mdg-hamburg.de/"
echo "   Click on any desktop type to launch"
echo

# Optional: Configure Apache SSL for these ports (not required but can provide SSL termination)
read -p "Do you want to configure Apache SSL termination for these ports? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo
    echo "To configure Apache SSL termination (optional):"
    echo
    echo "1. Create port listeners in Apache config:"
    echo "   Edit /etc/apache2/ports.conf (Debian/Ubuntu) or /etc/httpd/conf/httpd.conf (RHEL/CentOS)"
    echo
    cat << 'EOF'
   # Add these lines:
   Listen 7000
   Listen 7001
   Listen 7002
   # ... (or use a loop in bash to generate all)
EOF
    echo
    echo "2. Create virtual hosts:"
    echo
    cat << 'EOF'
   # In /etc/apache2/sites-available/kasmvnc-ports.conf (or equivalent):
   
   <VirtualHost *:7000>
       ServerName desktop.hub.mdg-hamburg.de
       
       SSLEngine on
       SSLCertificateFile /path/to/cert.pem
       SSLCertificateKeyFile /path/to/key.pem
       
       ProxyPreserveHost On
       ProxyPass / https://172.22.0.27:7000/ upgrade=any
       ProxyPassReverse / https://172.22.0.27:7000/
   </VirtualHost>
   
   # Repeat for other ports (7001, 7002, etc.)
EOF
    echo
    echo "3. Enable site and reload:"
    echo "   a2ensite kasmvnc-ports"
    echo "   systemctl reload apache2"
    echo
    echo "NOTE: This is optional. KasmVNC already provides SSL on these ports."
    echo "Apache SSL termination only needed if you want to centralize certificate management."
fi

echo
echo "Setup complete! Test the connection now."
