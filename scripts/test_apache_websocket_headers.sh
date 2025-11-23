#!/bin/bash
# Test script to verify Apache is forwarding WebSocket headers correctly
# This script tests the Apache configuration by making a WebSocket upgrade request
# and checking if the headers are being forwarded to Flask

set -e

echo "========================================="
echo "Apache WebSocket Header Forwarding Test"
echo "========================================="
echo ""

# Configuration
DOMAIN="${1:-localhost:5020}"
PROTOCOL="${2:-http}"
FULL_URL="${PROTOCOL}://${DOMAIN}/websockify"

echo "Testing WebSocket header forwarding to: $FULL_URL"
echo ""

# Test 1: Check if Apache/Flask is accessible
echo "Test 1: Basic connectivity check..."
if curl -s -o /dev/null -w "%{http_code}" "${PROTOCOL}://${DOMAIN}/health" 2>/dev/null | grep -q "200\|404"; then
    echo "✓ Server is reachable"
else
    echo "✗ Server is NOT reachable at ${PROTOCOL}://${DOMAIN}/health"
    echo "  Make sure the application is running"
    exit 1
fi
echo ""

# Test 2: Send WebSocket upgrade request and check response
echo "Test 2: Testing WebSocket header forwarding..."
echo "Sending WebSocket upgrade request..."

RESPONSE=$(curl -s -i -X GET "$FULL_URL" \
    -H "Upgrade: websocket" \
    -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    -H "Sec-WebSocket-Version: 13" \
    2>&1 || true)

echo ""
echo "Response received:"
echo "$RESPONSE" | head -20
echo ""

# Check for WebSocket upgrade acceptance (101 status)
if echo "$RESPONSE" | grep -q "101"; then
    echo "✓ WebSocket upgrade accepted (HTTP 101)"
    echo "  Headers are being forwarded correctly to Flask"
    exit 0
fi

# Check for container not found error (expected if no container is running)
if echo "$RESPONSE" | grep -q "Container not found"; then
    echo "✓ Flask received WebSocket headers correctly"
    echo "  (Container not found is expected if no desktop is running)"
    exit 0
fi

# Check if Flask detected the WebSocket request
if echo "$RESPONSE" | grep -q "WebSocket"; then
    echo "✓ Flask is processing WebSocket requests"
    echo "  Check Flask logs to see if 'WebSocket upgrade request detected' appears"
    exit 0
fi

# If we got a 200 OK, the headers might not be forwarded
if echo "$RESPONSE" | grep -q "200 OK"; then
    echo "✗ Headers NOT forwarded - Flask sees regular HTTP request"
    echo ""
    echo "This means Apache is NOT forwarding the Upgrade and Connection headers."
    echo "Please check your Apache configuration includes:"
    echo ""
    echo "  SetEnvIf Upgrade \"(?i)websocket\" IS_WEBSOCKET=1"
    echo "  SetEnvIf Connection \"(?i)upgrade\" IS_UPGRADE=1"
    echo "  RequestHeader set Upgrade \"websocket\" env=IS_WEBSOCKET"
    echo "  RequestHeader set Connection \"Upgrade\" env=IS_UPGRADE"
    echo ""
    echo "After updating, run:"
    echo "  sudo apache2ctl configtest"
    echo "  sudo systemctl reload apache2"
    exit 1
fi

echo "⚠ Unexpected response - please check Flask logs"
echo "Run: docker-compose logs -f app | grep websockify"
exit 1
