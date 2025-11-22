#!/bin/bash

# Script to generate self-signed SSL certificates for development/testing
# For production, use Let's Encrypt or your own certificates

SSL_DIR="./ssl"
DAYS=365

echo "Generating self-signed SSL certificate for development..."

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DIR"

# Generate private key and certificate
openssl req -x509 -nodes -days $DAYS -newkey rsa:2048 \
    -keyout "$SSL_DIR/key.pem" \
    -out "$SSL_DIR/cert.pem" \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Set proper permissions
chmod 600 "$SSL_DIR/key.pem"
chmod 644 "$SSL_DIR/cert.pem"

echo "✓ SSL certificates generated in $SSL_DIR/"
echo "  - Certificate: $SSL_DIR/cert.pem"
echo "  - Private Key: $SSL_DIR/key.pem"
echo ""
echo "Note: These are self-signed certificates for development only."
echo "For production, use Let's Encrypt or obtain certificates from a trusted CA."
