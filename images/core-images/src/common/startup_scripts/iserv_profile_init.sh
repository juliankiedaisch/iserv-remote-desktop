#!/usr/bin/env bash
# IServ Remote Desktop - Profile Initialization Script
# This script copies existing files from mounted directories TO /home/kasm-user
# at container startup, enabling persistent data across container restarts.
# - /home/kasm-user-private (user's private files) -> /home/kasm-user
# - /home/kasm-user-configs (desktop-specific configs) -> /home/kasm-user

set -e

HOME_DIR="/home/kasm-user"
PRIVATE_DIR="/home/kasm-user-private"
CONFIG_DIR="/home/kasm-user-configs"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting IServ profile initialization..."

# Check if sync directories are mounted
if [ ! -d "$PRIVATE_DIR" ]; then
    log "WARNING: Private directory not mounted at $PRIVATE_DIR, skipping private files initialization"
else
    log "Copying private files from $PRIVATE_DIR to $HOME_DIR"
    # Copy private files first (base layer)
    # Use -a to preserve permissions, -u to only copy newer files
    rsync -au "$PRIVATE_DIR/" "$HOME_DIR/" 2>/dev/null || true
    log "Private files copied"
fi

if [ ! -d "$CONFIG_DIR" ]; then
    log "WARNING: Config directory not mounted at $CONFIG_DIR, skipping config initialization"
else
    log "Copying config files from $CONFIG_DIR to $HOME_DIR"
    # Overlay configs without overwriting existing files (-n flag would skip existing, but rsync --ignore-existing is better)
    # We use --ignore-existing to not overwrite files already present
    rsync -a --ignore-existing "$CONFIG_DIR/" "$HOME_DIR/" 2>/dev/null || true
    log "Config files copied"
fi

log "IServ profile initialization completed successfully"
exit 0
