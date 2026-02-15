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
        # It's a directory - sync recursively with deletions
        rsync -a --update --delete "$item/" "$dest/" 2>/dev/null || true
    fi
done

# Sync visible files/folders to private directory
log "Syncing visible files to private directory..."

# Sync ALL non-hidden files and folders from home directory
# Exclude the Public folder - it contains read-only mounted assignment folders
find "$HOME_DIR" -maxdepth 1 ! -name ".*" ! -name "kasm-user" ! -name "Public" -print0 | while IFS= read -r -d '' item; do
    basename=$(basename "$item")
    dest="$PRIVATE_DIR/$basename"
    
    if [ -f "$item" ]; then
        # It's a file
        mkdir -p "$(dirname "$dest")"
        cp -a "$item" "$dest" 2>/dev/null || true
    elif [ -d "$item" ]; then
        # It's a directory - sync recursively with deletions
        mkdir -p "$dest"
        rsync -a --update --delete "$item/" "$dest/" 2>/dev/null || true
    fi
done

log "One-time profile sync completed successfully"
exit 0
