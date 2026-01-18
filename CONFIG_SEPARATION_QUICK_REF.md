# User Config Separation - Quick Reference

## What Changed?

User data is now separated into:
- **files/** - User's actual files (Documents, Downloads, etc.)
- **configs/{image}/** - Desktop settings per container image (user's personal copy)
- **/data/templates/{image}/** - Default settings from each image (centralized, shared across all users)

## Key Benefits

✅ Desktop settings persist across container restarts  
✅ Different images have different settings  
✅ Users can reset settings without losing files  
✅ Background, panel, and app settings are saved  

## For Users

### Reset Desktop Settings

Via API:
```bash
curl -X POST https://hub.mdg-hamburg.de/api/config/reset \
  -H "Content-Type: application/json" \
  -H "X-User-ID: YOUR_USER_ID" \
  -d '{"image_name": "teacherki/kasm-desktop:latest"}'
```

Your files in Documents, Downloads, etc. are NOT affected!

### Check Your Configs

```bash
curl https://hub.mdg-hamburg.de/api/config/list \
  -H "X-User-ID: YOUR_USER_ID"
```

## For Administrators

### Run Migration

First time setup - migrate existing users:
```bash
cd /root/iserv-remote-desktop/backend
python3 scripts/migrate_user_data_separation.py
```

### Refresh Config Template

After updating a container image:
```bash
curl -X POST https://hub.mdg-hamburg.de/api/config/templates/refresh \
  -H "Content-Type: application/json" \
  -H "X-User-ID: ADMIN_USER_ID" \
  -d '{"image_name": "teacherki/kasm-desktop:latest"}'
```

### Check User Directory

```bash
tree -L 3 /data/users/{user_id}/
```

Expected structure:
```
/data/users/{user_id}/
├── files/
│   ├── Desktop/
│   ├── Documents/
│   └── Downloads/
└── configs/
    └── teacherki-kasm-desktop-latest/
        ├── .config/
        └── .cache/

/data/templates/
└── teacherki-kasm-desktop-latest/
    ├── .config/
    ├── .cache/
    └── .template_initialized
```

## Config Files Locations

### Desktop Background
- **File**: `configs/{image}/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml`
- **Property**: `<property name="last-image" type="string" value="/path/to/wallpaper.png"/>`

### Bottom Panel/Dock
- **File**: `configs/{image}/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml`
- **Contains**: Launcher icons, panel position, system tray

### Application Menu Icon
- **Panel XML**: `<property name="button-icon" type="string" value="/path/to/icon.png"/>`

## Troubleshooting

### Settings not persisting?
```bash
# Check config directory exists
ls -la /data/users/{user_id}/configs/{image}/

# Check container mounts
docker inspect {container_id} | grep -A 20 Mounts
```

### Need to reset everything?
```bash
# Backup and remove configs
mv /data/users/{user_id}/configs/{image} \
   /data/users/{user_id}/configs/{image}.backup

# Next container start will use fresh template
```

### Template missing?
```bash
# Force re-extract from image
curl -X POST https://hub.mdg-hamburg.de/api/config/templates/refresh \
  -H "Content-Type: application/json" \
  -H "X-User-ID: ADMIN_ID" \
  -d '{"image_name": "teacherki/kasm-desktop:latest"}'
```

## Docker Manager Changes

### New Methods

- `_prepare_user_directories()` - Sets up file/config separation
- `_extract_config_template()` - Extracts defaults from image
- `_copy_template_to_user_config()` - Initializes user configs
- `reset_user_config()` - Resets to defaults with backup
- `refresh_config_template()` - Updates template from image

### Container Startup

Containers now run a startup script that merges configs:
```bash
cp -an /home/kasm-user-configs/. /home/kasm-user/
```

The `-n` flag prevents overwriting user changes!

## See Also

- [USER_CONFIG_SEPARATION.md](USER_CONFIG_SEPARATION.md) - Full documentation
- [FILE_MANAGER.md](FILE_MANAGER.md) - File management API
