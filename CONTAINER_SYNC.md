# Container Profile Synchronization

## Overview

The IServ Remote Desktop implements a bidirectional synchronization mechanism to persist changes made within containers back to the host filesystem. This ensures that user data and configurations are preserved across container restarts and handles multiple concurrent containers gracefully.

## How It Works

### Directory Structure

Each container has three key directories:

1. **`/home/kasm-user`** - The container's home directory where users work
2. **`/home/kasm-user-private`** - Mounted from host: `/data/users/{user_id}/PRIVATE/`
   - Contains user's files (Desktop, Documents, Downloads, etc.)
   - Shared across all containers for the user
3. **`/home/kasm-user-configs`** - Mounted from host: `/data/users/{user_id}/{desktop_type}/`
   - Contains desktop-specific configurations (.config, .cache, etc.)
   - Separate for each desktop type (ubuntu-desktop, filius-desktop, etc.)

### Synchronization Flow

#### On Container Startup

1. **Initial Copy** - Files are copied FROM mounted directories TO `/home/kasm-user`:
   ```bash
   # Copy private files first (base layer) - uses rsync for better performance
   rsync -au /home/kasm-user-private/ /home/kasm-user/
   
   # Overlay configs (without overwriting existing files)
   rsync -a --ignore-existing /home/kasm-user-configs/ /home/kasm-user/
   ```

2. **Background Sync Starts** - The `iserv_profile_sync.sh` script starts:
   - Runs in the background
   - Syncs changes every 30 seconds (configurable)
   - Monitors for shutdown signals

#### During Container Runtime

The background sync continuously copies changes FROM `/home/kasm-user` BACK to mounted directories:

- **Hidden files/folders** (`.config`, `.bashrc`, etc.) → `/home/kasm-user-configs/` (desktop-specific)
- **Visible files/folders** (Desktop, Documents, etc.) → `/home/kasm-user-private/` (shared)

#### On Container Shutdown

1. **Stop Background Sync** - Sends SIGTERM to background sync process
2. **Final Sync** - Runs `iserv_profile_sync_once.sh` to ensure all changes are saved
3. **Container Stops** - All data is persisted to host

### Conflict Resolution

When multiple containers run simultaneously, conflicts can occur when both modify the same file. The sync mechanism resolves this by:

**Newest File Wins** - Uses `rsync --update` which only copies files that are newer than the destination:
```bash
rsync -a --update /home/kasm-user/.config/ /home/kasm-user-configs/ 
```

This means:
- If Container A modifies `file.txt` at 10:00
- And Container B modifies the same file at 10:05
- Container B's version will be kept (it's newer)
- No user prompts or manual intervention required

## Configuration

### Environment Variables

The sync mechanism can be controlled via environment variables in `docker_manager.py`:

```python
environment = {
    'ISERV_PROFILE_SYNC': '1',        # Enable (1) or disable (0) sync
    'ISERV_SYNC_INTERVAL': '30',      # Sync interval in seconds (default: 30)
}
```

### Global Configuration

You can also set these in your `.env` file:

```bash
ISERV_SYNC_INTERVAL=30  # Adjust sync frequency
```

## File Categorization

### Hidden Files/Folders → Config Directory

Synced to `/home/kasm-user-configs/` (desktop-specific):

- `.config/` - Application configurations
- `.cache/` - Application caches
- `.local/` - Local user data
- `.bashrc`, `.profile` - Shell configurations
- `.mozilla/`, `.pki/` - Browser/certificate data
- `.vnc/` - VNC settings
- `.kasmpasswd` - Kasm password file
- And all other dot files/folders

### Visible Files/Folders → Private Directory

Synced to `/home/kasm-user-private/` (shared across desktops):

- `Desktop/` - Desktop files
- `Documents/` - User documents
- `Downloads/` - Downloaded files
- `Music/` - Music files
- `Pictures/` - Image files
- `Videos/` - Video files
- `Public/` - Public files
- `PDF/` - PDF files
- Any other non-hidden files in home directory

## Implementation Details

### Scripts

#### `iserv_profile_init.sh`
Initial profile setup script that runs once at container startup:
- Copies files FROM mounted directories TO `/home/kasm-user`
- Uses rsync to preserve permissions and handle existing files
- Runs before any services start to ensure user data is available
- Copies private files first, then overlays config files

#### `iserv_profile_sync.sh`
Background daemon that performs continuous synchronization:
- Runs in an infinite loop
- Syncs every `ISERV_SYNC_INTERVAL` seconds
- Handles SIGTERM for graceful shutdown
- Saves PID to `/tmp/.iserv_profile_sync.pid`
- Uses lock file to prevent concurrent syncs

#### `iserv_profile_sync_once.sh`
One-time sync script for shutdown:
- Called during container shutdown
- Performs a single comprehensive sync
- Ensures all changes are persisted

### Integration Points

#### `vnc_startup.sh`
Container startup script that:
- Calls `iserv_profile_init.sh` to initialize user home from mounted directories
- Starts the background sync after all services are running
- Monitors the sync process and restarts if needed
- Adds sync to the `KASM_PROCS` array for monitoring

#### `kasm_pre_shutdown_user.sh`
Container shutdown hook that:
- Stops the background sync process
- Runs final one-time sync
- Ensures clean shutdown

## Advantages

### For Users

1. **Automatic Persistence** - Changes are saved automatically without user action
2. **No Data Loss** - Regular syncing minimizes data loss risk
3. **Multiple Containers** - Can run multiple desktops simultaneously
4. **Seamless Experience** - Sync happens in background, no interruption

### For Administrators

1. **No User Prompts** - Conflicts resolved automatically
2. **Configurable** - Sync interval can be adjusted
3. **Robust** - Handles failures gracefully
4. **Separated Data** - Configs and files are logically separated

## Monitoring and Debugging

### Check Sync Status

View sync logs in container:
```bash
docker logs <container_id> | grep "IServ profile sync"
```

### Check Sync Process

Inside container:
```bash
ps aux | grep iserv_profile_sync
cat /tmp/.iserv_profile_sync.pid
```

### Manual Sync Trigger

If needed, manually trigger initialization or sync inside container:
```bash
# Initial copy from mounted dirs to home (normally happens at startup)
/dockerstartup/iserv_profile_init.sh

# One-time sync from home to mounted dirs
/dockerstartup/iserv_profile_sync_once.sh
```

### Disable Sync

To disable sync for a specific container, set environment variable to 0:
```python
environment = {
    'ISERV_PROFILE_SYNC': '0',  # Disable sync
}
```

## Troubleshooting

### Sync Not Working

1. **Check if directories are mounted**:
   ```bash
   docker exec <container_id> ls -la /home/kasm-user-private
   docker exec <container_id> ls -la /home/kasm-user-configs
   ```

2. **Check sync process is running**:
   ```bash
   docker exec <container_id> ps aux | grep iserv_profile_sync
   ```

3. **Check sync logs**:
   ```bash
   docker logs <container_id> 2>&1 | grep -i sync
   ```

### Permission Issues

If files have wrong permissions:
```bash
# On host
chown -R 1000:1000 /data/users/{user_id}/PRIVATE
chown -R 1000:1000 /data/users/{user_id}/{desktop_type}
```

### Conflicts Not Resolving

The sync uses `rsync --update` which only copies newer files. If you want to force a sync:
```bash
# Inside container
rsync -av /home/kasm-user/.config/ /home/kasm-user-configs/
rsync -av /home/kasm-user/Documents/ /home/kasm-user-private/Documents/
```

## Performance Considerations

### Sync Interval

- **Default: 30 seconds** - Good balance between performance and data safety
- **Lower values (10-15s)** - Better for frequent changes, higher I/O load
- **Higher values (60-120s)** - Lower I/O load, risk of more data loss on crash

### Network/Shared Storage

If using network-attached storage (NFS, CIFS):
- Consider increasing sync interval to reduce network traffic
- Monitor network I/O during sync operations

### Large Directories

For users with large home directories:
- Sync may take longer
- Consider excluding large cache directories
- Monitor disk I/O

## Future Enhancements

Possible improvements for future versions:

1. **Smart Sync** - Only sync changed files (inotify-based)
2. **Selective Sync** - Allow users to exclude specific directories
3. **Compression** - Compress data during sync for network storage
4. **Versioning** - Keep multiple versions of files
5. **Conflict UI** - Optional UI to let users choose conflict resolution
6. **Metrics** - Collect sync metrics for monitoring
7. **Throttling** - Rate limit sync to prevent I/O storms

## Related Documentation

- [USER_CONFIG_SEPARATION.md](USER_CONFIG_SEPARATION.md) - Config separation architecture
- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall system architecture
- [DOCKER_COMPOSE_GUIDE.md](DOCKER_COMPOSE_GUIDE.md) - Docker setup guide
