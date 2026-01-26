#!/usr/bin/env bash
# IServ Remote Desktop - Profile Synchronization Script
# This script syncs changes from /home/kasm-user back to mounted directories
# - Hidden files/folders -> /home/kasm-user-configs (desktop-specific configs)
# - Regular files/folders -> /home/kasm-user-private (user's private files)
# Handles multiple concurrent containers by preferring newer files

set -e

SYNC_INTERVAL="${ISERV_SYNC_INTERVAL:-30}"  # Sync every 30 seconds by default
LOCK_FILE="/tmp/.iserv_profile_sync.lock"
PID_FILE="/tmp/.iserv_profile_sync.pid"
HOME_DIR="/home/kasm-user"
PRIVATE_DIR="/home/kasm-user-private"
CONFIG_DIR="/home/kasm-user-configs"

# Save PID for graceful shutdown
echo $$ > "$PID_FILE"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if sync directories are mounted
check_mounts() {
    if [ ! -d "$PRIVATE_DIR" ]; then
        log "ERROR: Private directory not mounted at $PRIVATE_DIR"
        return 1
    fi
    
    if [ ! -d "$CONFIG_DIR" ]; then
        log "ERROR: Config directory not mounted at $CONFIG_DIR"
        return 1
    fi
    
    return 0
}

# Sync a single file with conflict resolution (newer wins)
sync_file() {
    local src="$1"
    local dest="$2"
    
    # Create destination directory if needed
    mkdir -p "$(dirname "$dest")"
    
    # If destination doesn't exist, just copy
    if [ ! -e "$dest" ]; then
        cp -a "$src" "$dest" 2>/dev/null || true
        return 0
    fi
    
    # Both exist - compare modification times
    if [ "$src" -nt "$dest" ]; then
        # Source is newer, copy it
        cp -a "$src" "$dest" 2>/dev/null || true
    fi
    
    return 0
}

# Sync hidden files/folders to config directory
sync_hidden_to_config() {
    log "Syncing hidden files to config directory..."
    
    # Find all hidden items in home directory (exclude . and ..)
    find "$HOME_DIR" -maxdepth 1 -name ".*" ! -name "." ! -name ".." -print0 | while IFS= read -r -d '' item; do
        local basename=$(basename "$item")
        local dest="$CONFIG_DIR/$basename"
        
        if [ -f "$item" ]; then
            # It's a file
            sync_file "$item" "$dest"
        elif [ -d "$item" ]; then
            # It's a directory - sync recursively with deletions
            rsync -a --update --delete "$item/" "$dest/" 2>/dev/null || true
        fi
    done
}

# Sync visible files/folders to private directory
sync_visible_to_private() {
    log "Syncing visible files to private directory..."
    
    # Sync ALL non-hidden files and folders from home directory
    find "$HOME_DIR" -maxdepth 1 ! -name ".*" ! -name "kasm-user" -print0 | while IFS= read -r -d '' item; do
        local basename=$(basename "$item")
        local dest="$PRIVATE_DIR/$basename"
        
        if [ -f "$item" ]; then
            # It's a file
            sync_file "$item" "$dest"
        elif [ -d "$item" ]; then
            # It's a directory - sync recursively with deletions
            mkdir -p "$dest"
            rsync -a --update --delete "$item/" "$dest/" 2>/dev/null || true
        fi
    done
}

# Perform full sync
perform_sync() {
    # Acquire lock to prevent concurrent syncs
    if [ -f "$LOCK_FILE" ]; then
        log "Sync already in progress, skipping..."
        return 0
    fi
    
    touch "$LOCK_FILE"
    
    # Check if mounts are available
    if ! check_mounts; then
        rm -f "$LOCK_FILE"
        return 1
    fi
    
    # Sync hidden files to config
    sync_hidden_to_config
    
    # Sync visible files to private
    sync_visible_to_private
    
    rm -f "$LOCK_FILE"
    log "Sync completed successfully"
    return 0
}

# Handle shutdown signal - perform final sync
handle_shutdown() {
    log "Shutdown signal received, performing final sync..."
    perform_sync
    rm -f "$PID_FILE"
    log "Final sync completed, exiting"
    exit 0
}

# Trap shutdown signals
trap handle_shutdown SIGTERM SIGINT SIGQUIT

# Main sync loop
log "IServ Profile Sync started (interval: ${SYNC_INTERVAL}s)"
log "Home: $HOME_DIR"
log "Private: $PRIVATE_DIR"
log "Config: $CONFIG_DIR"

# Perform initial sync after a short delay (let container initialize)
sleep 5
perform_sync

# Continuous sync loop
while true; do
    sleep "$SYNC_INTERVAL"
    perform_sync || log "Sync failed, will retry..."
done
