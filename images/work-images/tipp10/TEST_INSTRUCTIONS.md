# Testing Kasm Tipp10 Image

This directory contains a docker-compose setup for manually testing the Tipp10 desktop image.

## Quick Start

1. **Build and start the container:**
   ```bash
   docker-compose -f docker-compose-test.yml up --build
   ```

2. **Access the desktop:**
   - Open browser: https://localhost:6901
   - Password: `password`
   - User: `testuser`

3. **Stop the container:**
   ```bash
   docker-compose -f docker-compose-test.yml down
   ```

## Volume Structure

The test setup uses three volumes that mirror the production setup:

### 1. `test-volumes/user-private/`
- **Purpose:** User's personal files shared across all desktop types
- **Contains:** Desktop, Documents, Downloads, Pictures, Videos, Music, Public, PDF folders
- **Mounted at:** `/home/kasm-user-private` (merged into `/home/kasm-user` at startup)

### 2. `test-volumes/user-configs/`
- **Purpose:** Desktop-type-specific configurations
- **Contains:** `.config/`, `.cache/`, `.local/`, application settings
- **Mounted at:** `/home/kasm-user-configs` (overlaid into `/home/kasm-user` at startup)
- **Note:** Each desktop type has its own config directory in production

### 3. `test-volumes/shared-public/`
- **Purpose:** Shared public files accessible to all users
- **Mounted at:** `/home/kasm-user/Public/shared`

## Testing Scenarios

### Test German Locale
1. Start the container and access via browser
2. Launch Tipp10 from the application menu
3. Verify that Tipp10 interface is in German
4. Check: Settings, menus, help text should all be German

### Test Persistent Data
1. Create files in Documents folder
2. Modify Tipp10 settings
3. Stop container: `docker-compose -f docker-compose-test.yml down`
4. Start again: `docker-compose -f docker-compose-test.yml up`
5. Verify: Files and settings are preserved

### Test Custom Startup Script
1. Check if `/dockerstartup/custom_startup.sh` is executed
2. Verify application launches automatically if configured

### Clean Start (Reset Volumes)
```bash
docker-compose -f docker-compose-test.yml down
rm -rf test-volumes/
docker-compose -f docker-compose-test.yml up --build
```

## Environment Variables

Key environment variables (can be modified in docker-compose-test.yml):
- `VNC_PW`: Password for VNC access (default: `password`)
- `LANG`, `LANGUAGE`, `LC_ALL`: German locale settings
- `START_PULSEAUDIO`: Enable audio support
- `ISERV_PROFILE_SYNC`: Enable profile synchronization

## Troubleshooting

### Tipp10 still in English?
- Check locale is generated: `docker exec kasm-tipp10-test locale -a | grep de_DE`
- Check language pack installed: `docker exec kasm-tipp10-test dpkg -l | grep language-pack-de`

### Permission Issues
- The container runs as UID 1000
- Check volume permissions: `ls -la test-volumes/`
- Fix: `sudo chown -R 1000:1000 test-volumes/`

### Port Already in Use
- If port 6901 is busy, modify the ports section in docker-compose-test.yml:
  ```yaml
  ports:
    - "7901:6901"  # Change host port
  ```

## Building Without Starting

Build the image without starting:
```bash
docker-compose -f docker-compose-test.yml build
```

Tag and push to registry:
```bash
docker tag teacherki/kasm-tipp10:latest teacherki/kasm-tipp10:v1.0
docker push teacherki/kasm-tipp10:latest
```

## Logs

View container logs:
```bash
docker-compose -f docker-compose-test.yml logs -f
```

Check specific processes:
```bash
docker exec kasm-tipp10-test ps aux
```
