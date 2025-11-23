#!/bin/bash
# Script to validate Apache configuration for WebSocket header forwarding

echo "=========================================="
echo "Apache WebSocket Configuration Validator"
echo "=========================================="
echo ""

# Check if Apache is installed
if ! command -v apache2ctl &> /dev/null && ! command -v apachectl &> /dev/null; then
    echo "❌ Apache is not installed or not in PATH"
    exit 1
fi

APACHE_CMD="apache2ctl"
if ! command -v apache2ctl &> /dev/null; then
    APACHE_CMD="apachectl"
fi

echo "✓ Apache found: $APACHE_CMD"
echo ""

# Check required modules
echo "Checking required Apache modules..."
MODULES_OK=true

check_module() {
    local module=$1
    if $APACHE_CMD -M 2>/dev/null | grep -q "${module}_module"; then
        echo "  ✓ $module"
    else
        echo "  ❌ $module (not enabled)"
        MODULES_OK=false
    fi
}

check_module "proxy"
check_module "proxy_http"
check_module "proxy_wstunnel"
check_module "rewrite"
check_module "headers"
check_module "ssl"

echo ""

if [ "$MODULES_OK" = false ]; then
    echo "❌ Some required modules are not enabled"
    echo ""
    echo "To enable missing modules, run:"
    echo "  sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers ssl"
    echo "  sudo systemctl restart apache2"
    exit 1
fi

# Test Apache configuration syntax
echo "Testing Apache configuration syntax..."
if sudo $APACHE_CMD configtest 2>&1 | grep -q "Syntax OK"; then
    echo "  ✓ Apache configuration syntax is OK"
else
    echo "  ❌ Apache configuration has syntax errors"
    echo ""
    echo "Run the following to see details:"
    echo "  sudo $APACHE_CMD configtest"
    exit 1
fi

echo ""

# Check if the WebSocket configuration exists
echo "Checking for WebSocket header forwarding configuration..."

APACHE_CONF_DIRS=(
    "/etc/apache2/sites-available"
    "/etc/apache2/sites-enabled"
    "/etc/httpd/conf.d"
    "/etc/httpd/sites-available"
    "/etc/httpd/sites-enabled"
)

FOUND_CONFIG=false
for dir in "${APACHE_CONF_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Use nullglob to handle case where no .conf files exist
        # Use subshell to ensure shopt changes don't affect parent shell
        (
            shopt -s nullglob
            for conf in "$dir"/*.conf; do
                # Look for the environment variable pattern in RewriteRule
                # Pattern: E=UPGRADE:%{HTTP:Upgrade} (with optional spacing)
                # Using [[:space:]] for POSIX compliance instead of \s
                if grep -iE "E=UPGRADE[[:space:]]*:[[:space:]]*%\{HTTP:Upgrade\}" "$conf" &>/dev/null; then
                    echo "  ✓ WebSocket header forwarding found in: $conf"
                    FOUND_CONFIG=true
                    
                    # Check for both environment variable and RequestHeader
                    if grep -iE "RequestHeader[[:space:]]+set[[:space:]]+Upgrade" "$conf" &>/dev/null; then
                        echo "  ✓ Upgrade header forwarding configured"
                    else
                        echo "  ⚠️  Missing 'RequestHeader set Upgrade' directive"
                    fi
                    
                    if grep -iE "RequestHeader[[:space:]]+set[[:space:]]+Connection" "$conf" &>/dev/null; then
                        echo "  ✓ Connection header forwarding configured"
                    else
                        echo "  ⚠️  Missing 'RequestHeader set Connection' directive"
                    fi
                fi
            done
        )
    fi
done

if [ "$FOUND_CONFIG" = false ]; then
    echo "  ⚠️  WebSocket header forwarding configuration not found"
    echo ""
    echo "Your Apache configuration should include:"
    echo "  RewriteCond %{HTTP:Upgrade} =websocket [NC]"
    echo "  RewriteCond %{HTTP:Connection} upgrade [NC]"
    echo "  RewriteRule ^/(.*) http://localhost:5020/\$1 [P,L,E=UPGRADE:%{HTTP:Upgrade},E=CONNECTION:%{HTTP:Connection}]"
    echo "  RequestHeader set Upgrade %{UPGRADE}e env=UPGRADE"
    echo "  RequestHeader set Connection %{CONNECTION}e env=CONNECTION"
    echo ""
    echo "See apache.conf in this repository for the complete configuration."
fi

echo ""
echo "=========================================="
echo "Validation complete!"
echo "=========================================="

if [ "$MODULES_OK" = true ] && [ "$FOUND_CONFIG" = true ]; then
    echo "✓ All checks passed"
    echo ""
    echo "Next steps:"
    echo "1. Reload Apache: sudo systemctl reload apache2"
    echo "2. Test WebSocket connection by starting a container"
    echo "3. Check Flask logs: docker-compose logs -f app | grep websockify"
    echo "4. Look for 'WebSocket upgrade request detected' in the logs"
    exit 0
else
    echo "⚠️  Some issues were found. Please review the output above."
    exit 1
fi
