# Centralized Template System - Summary

## Changes Made

The config template system has been updated to use a **centralized template directory** instead of per-user templates.

### Key Changes

1. **Config Added** ([config.py](backend/app/config.py))
   - Added `EXTERN_TEMPLATE_DATA_BASE_DIR` environment variable

2. **Docker Manager Updated** ([docker_manager.py](backend/app/services/docker_manager.py))
   - Templates now stored in `/data/templates/{image}/` (centralized)
   - User configs remain in `/data/users/{user_id}/configs/{image}/` (personal)
   - When user starts container, template is copied from centralized location
   - Reset function fetches from centralized template
   - Refresh function updates centralized template only

3. **API Routes Updated** ([config_routes.py](backend/app/routes/config_routes.py))
   - Template checks now look at centralized location
   - Config info shows 'centralized' template location

4. **Documentation Updated**
   - [USER_CONFIG_SEPARATION.md](USER_CONFIG_SEPARATION.md)
   - [CONFIG_SEPARATION_QUICK_REF.md](CONFIG_SEPARATION_QUICK_REF.md)

## Directory Structure

### Before (Per-User Templates)
```
/data/users/{user_id}/
├── files/
├── configs/{image}/
└── config_templates/{image}/  ❌ Duplicated per user
```

### After (Centralized Templates)
```
/data/users/{user_id}/
├── files/
└── configs/{image}/            ✅ User's personal copy

/data/templates/                ✅ Shared by all users
└── {image}/
    └── .template_initialized
```

## Benefits

✅ **Disk Efficiency**: One template serves all users (no duplication)  
✅ **Easier Management**: Update template once, affects all new containers  
✅ **Clearer Separation**: User data vs. system templates  
✅ **Centralized Control**: Admins manage templates in one location  
✅ **Security**: Users can't modify templates, only their own configs  

## How It Works

### First Container Start
1. User starts container with image X
2. System checks if `/data/templates/X/` exists
3. If not, extract template from image to `/data/templates/X/`
4. Copy template to user's `/data/users/{user_id}/configs/X/`
5. Mount user's config directory into container

### Subsequent Starts
1. User starts container with image X
2. Template already exists in `/data/templates/X/`
3. User's configs exist in `/data/users/{user_id}/configs/X/`
4. Mount user's existing configs (settings persist)

### Config Reset
1. User requests reset for image X
2. Backup current configs to `.backup.{timestamp}`
3. Copy fresh configs from `/data/templates/X/`
4. Next container start uses reset configs

### Template Refresh (Admin)
1. Admin requests template refresh for image X
2. Pull latest version of image
3. Backup old template to `.backup.{timestamp}`
4. Extract new template to `/data/templates/X/`
5. Existing user configs unchanged (users keep their settings)
6. New users or reset users get new template

## Migration

Existing users with old structure will work transparently:
- System checks centralized location first
- If template missing, creates it automatically
- No manual migration needed for templates

## Environment Variables

Add to your `.env` or Docker Compose:

```bash
# Backend view (inside container)
TEMPLATE_DATA_BASE_DIR=/data/templates

# External view (on host)
EXTERN_TEMPLATE_DATA_BASE_DIR=/data/templates
```

## Permissions

Templates should be readable by container user:
```bash
chown -R 1000:1000 /data/templates
chmod -R 755 /data/templates
```

## Testing

1. Start a container with a new image
2. Check `/data/templates/{image}/` was created
3. Check `/data/users/{user_id}/configs/{image}/` has configs
4. Make changes to desktop settings
5. Stop and restart container - settings should persist
6. Reset config via API - should get fresh copy from `/data/templates/`

## Rollback

If you need to revert to per-user templates, restore the backup of docker_manager.py and config_routes.py from git history.
