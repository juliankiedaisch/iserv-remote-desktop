# User Data and Configuration Separation

## Overview

This system separates user files from container-specific configurations, allowing users to:
- Have persistent desktop settings per container image
- Keep their files separate from container configs
- Reset desktop settings to defaults without losing files
- Have different desktop configurations for different container types

## Directory Structure

### New Structure (After Migration)

```
/data/users/{user_id}/
├── files/                          # User's actual files
│   ├── Desktop/
│   ├── Documents/
│   ├── Downloads/
│   ├── Music/
│   ├── Pictures/
│   ├── Videos/
│   ├── Public/
│   └── PDF/
└── configs/                        # Image-specific configs (user's copy)
    ├── teacherki-kasm-desktop-latest/
    │   ├── .config/               # XFCE settings, app configs
    │   ├── .cache/
    │   ├── .local/
    │   ├── .bashrc
    │   └── ...                    # Other hidden config files
    └── teacherki-kasm-filius-latest/
        ├── .config/
        └── ...

/data/templates/                    # Centralized templates (shared across all users)
├── teacherki-kasm-desktop-latest/
│   ├── .config/
│   ├── .cache/
│   ├── .template_initialized
│   └── ...
└── teacherki-kasm-filius-latest/
    └── ...
```

### How It Works

1. **Container Startup**: When a container starts:
   - User's `files/` directory is mounted to `/home/kasm-user`
   - Image-specific configs from `configs/{image}/` are mounted to `/home/kasm-user-configs`
   - A startup script merges configs into the home directory
   - User sees their files + image-specific desktop settings

2. **Config Changes**: When a user changes desktop settings:
   - Changes are saved to their personal `configs/{image}/` directory
   - Next time the same image starts, settings persist
   - Different images have separate configs

3. **Config Reset**: Users can reset to defaults:
   - Original configs are backed up
   - Fresh configs are copied from centralized `/data/templates/{image}/`
   - Next container start uses fresh settings

4. **Template Management**: Centralized templates in `/data/templates/`:
   - Extracted once per image (shared across all users)
   - When a user first starts an image, template is copied to their `configs/`
   - Admins can refresh templates after image updates
   - No duplication - one template serves all users

## Desktop Background and Panel Configuration

### Background Settings
Located in: `.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml`

```xml
<property name="last-image" type="string" value="/usr/share/backgrounds/bg_default.png"/>
```

### Panel/Dock Settings
Located in: `.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml`

Contains:
- Panel position and size
- Application launchers (dock icons)
- System tray plugins
- Menu button icon

## Migration

### Automatic Migration on First Start

The system automatically:
1. Detects old structure (files directly in `/data/users/{user_id}/`)
2. Creates new directories (`files/`, `configs/`, `config_templates/`)
3. Moves user files to `files/`
4. Moves config files to `configs/default/`

### Manual Migration Script

For bulk migration or troubleshooting:

```bash
cd /root/iserv-remote-desktop/backend
python scripts/migrate_user_data_separation.py
```

The script will:
- List all users to migrate
- Ask for confirmation
- Move files to new structure
- Preserve permissions and ownership
- Report success/failure for each user

## API Endpoints

### Reset User Config

Reset a user's desktop settings to default template:

```http
POST /api/config/reset
Content-Type: application/json
X-User-ID: {user_id}

{
  "image_name": "teacherki/kasm-desktop:latest"
}
```

Response:
```json
{
  "success": true,
  "message": "Config reset to default for teacherki/kasm-desktop:latest",
  "backup": "/data/users/{user_id}/configs/teacherki-kasm-desktop-latest.backup.20260118_123456"
}
```

### List User Configs

Get all config directories for a user:

```http
GET /api/config/list
X-User-ID: {user_id}
```

Response:
```json
{
  "success": true,
  "configs": [
    {
      "image_dir": "teacherki-kasm-desktop-latest",
      "image_name": "teacherki/kasm-desktop:latest",
      "display_name": "Ubuntu Desktop",
      "has_template": true
    }
  ]
}
```

### Refresh Config Template (Admin Only)

Re-extract default configs from an image to centralized location:

```http
POST /api/config/templates/refresh
Content-Type: application/json
X-User-ID: {admin_user_id}

{
  "image_name": "teacherki/kasm-desktop:latest"
}
```

Response:
```json
{
  "success": true,
  "message": "Centralized config template refreshed for teacherki/kasm-desktop:latest",
  "template_location": "/data/templates/teacherki-kasm-desktop-latest"
}
```

## Implementation Details

### Config Extraction Process

When an image is first used:

1. **Create Temporary Container**: A temporary container is created from the image
2. **Start and Initialize**: Container starts and runs initialization scripts
3. **Extract Configs**: Hidden files and directories are extracted:
   - `.config/` - Application settings
   - `.cache/` - Application caches
   - `.local/` - User-local data
   - `.bashrc`, `.profile` - Shell configs
   - `.vnc/` - VNC settings
   - And more...
4. **Save as Centralized Template**: Extracted configs are saved to `/data/templates/{image}/`
5. **Mark Complete**: `.template_initialized` marker file is created
6. **First User Access**: When first user starts this image, template is copied to their `configs/`

### Template Distribution

- **Centralized Location**: `/data/templates/{image_name}/` - One copy for all users
- **User Copy**: `/data/users/{user_id}/configs/{image_name}/` - Personal, modifiable copy
- **On First Start**: Template automatically copied to user's directory
- **On Reset**: Fresh copy from centralized template replaces user's configs

### Config Patterns

Files/directories that are treated as configs:
```python
CONFIG_PATTERNS = [
    '.config', '.cache', '.local', '.mozilla', '.pki', '.vnc',
    '.bashrc', '.bash_profile', '.profile', '.Xauthority', '.ICEauthority',
    '.gtkrc-2.0', '.kasmpasswd', '.wget-hsts', '.gnupg', '.ssh',
    '.java', '.filius', '.vscode', '.launchpadlib', '.gvfs'
]
```

### Startup Script

The container startup script (`/bin/bash -c`):
```bash
#!/bin/bash
# Merge image-specific configs into user home
if [ -d /home/kasm-user-configs ]; then
  cp -an /home/kasm-user-configs/. /home/kasm-user/ 2>/dev/null || true
fi
# Execute original entrypoint
exec /dockerstartup/kasm_default_profile.sh /dockerstartup/vnc_startup.sh
```

The `-n` flag prevents overwriting existing files, so user changes persist.

## Benefits

### For Users
- **Persistent Settings**: Desktop wallpaper, panel layout, app preferences persist across sessions
- **Per-Image Configs**: Different desktops can have different settings
- **Easy Reset**: Can reset to defaults without losing files
- **Clean Separation**: Files and configs don't mix

### For Administrators
- **Centralized Management**: One template location for all users
- **Easier Updates**: Refresh template once, all new containers use updated configs
- **Better Debugging**: Config issues can be traced to centralized template
- **Disk Efficiency**: No duplicate templates per user
- **Scalable**: New images automatically extract to centralized location

## Troubleshooting

### Configs Not Persisting

1. Check if config directory exists:
   ```bash
   ls -la /data/users/{user_id}/configs/{image}/
   ```

2. Check volume mounts in running container:
   ```bash
   docker inspect {container_id} | grep -A 10 "Mounts"
   ```

3. Check startup logs:
   ```bash
   docker logs {container_id} | head -20
   ```

### Template Not Found

Recreate template:
```bash
# Via API (admin only)
curl -X POST https://hub.mdg-hamburg.de/api/config/templates/refresh \
  -H "Content-Type: application/json" \
  -H "X-User-ID: {admin_user_id}" \
  -d '{"image_name": "teacherki/kasm-desktop:latest"}'
```

### Migration Issues

Check migration script output:
```bash
python scripts/migrate_user_data_separation.py
```

Manual fix if needed:
```bash
# Create new structure
mkdir -p /data/users/{user_id}/{files,configs,config_templates}

# Move files manually
mv /data/users/{user_id}/Documents /data/users/{user_id}/files/
mv /data/users/{user_id}/.config /data/users/{user_id}/configs/default/
```

## Future Enhancements

- [ ] Config diff/comparison tool
- [ ] Export/import configs between users
- [ ] Config versioning and rollback
- [ ] UI for config management
- [ ] Shared config templates across multiple images
- [ ] Config sync across devices
