#!/usr/bin/env bash
# IServ Remote Desktop - One-time Profile Synchronization Script
# This script performs a single sync from /home/kasm-user to mounted directories
# Used during container shutdown to ensure all changes are persisted

set -e

HOME_DIR="/home/kasm-user"
PRIVATE_DIR="/home/kasm-user-private"
CONFIG_DIR="/home/kasm-user-configs"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if sync directories are mounted
if [ ! -d "$PRIVATE_DIR" ] || [ ! -d "$CONFIG_DIR" ]; then
    log "ERROR: Sync directories not mounted"
    exit 1
fi

log "Starting one-time profile sync..."

# Sync hidden files/folders to config directory
log "Syncing hidden files to config directory..."
find "$HOME_DIR" -maxdepth 1 -name ".*" ! -name "." ! -name ".." -print0 | while IFS= read -r -d '' item; do
    basename=$(basename "$item")
    dest="$CONFIG_DIR/$basename"
    
    if [ -f "$item" ]; then
        # It's a file
        mkdir -p "$(dirname "$dest")"
        cp -a "$item" "$dest" 2>/dev/null || true
    elif [ -d "$item" ]; then
        # It's a directory - sync recursively
        rsync -a --update "$item/" "$dest/" 2>/dev/null || true
    fi
done

# Sync visible files/folders to private directory
log "Syncing visible files to private directory..."
dirs=("Desktop" "Documents" "Downloads" "Music" "Pictures" "Videos" "Public" "PDF")

for dir in "${dirs[@]}"; do
    src="$HOME_DIR/$dir"
    dest="$PRIVATE_DIR/$dir"
    
    if [ -d "$src" ]; then
        # Sync directory contents with conflict resolution
        mkdir -p "$dest"
        rsync -a --update "$src/" "$dest/" 2>/dev/null || true
    fi
done

# Also sync any other non-hidden files in home directory
find "$HOME_DIR" -maxdepth 1 ! -name ".*" ! -name "kasm-user" -type f -print0 | while IFS= read -r -d '' file; do
    basename=$(basename "$file")
    dest="$PRIVATE_DIR/$basename"
    mkdir -p "$(dirname "$dest")"
    cp -a "$file" "$dest" 2>/dev/null || true
done

log "One-time profile sync completed successfully"
exit 0
