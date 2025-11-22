# Quick Start Guide - Reverse Proxy Setup

## TL;DR - Get Started in 5 Minutes

### 1. Configure Your Environment
```bash
cp .env.example .env
# Edit .env and set:
# - DOCKER_HOST_URL=your-domain.com (or localhost for testing)
# - OAuth credentials
# - Database settings
```

### 2. Start the Application
```bash
docker-compose up -d
```

### 3. Access Your Desktop
After logging in, containers are accessible at:
```
http://your-domain.com/desktop/{your-username}-{desktop-type}
```

Example: `http://example.com/desktop/alice-ubuntu-vscode`

## URL Format Examples

| User | Desktop Type | URL |
|------|-------------|-----|
| alice | ubuntu-vscode | `http://example.com/desktop/alice-ubuntu-vscode` |
| bob | ubuntu-desktop | `http://example.com/desktop/bob-ubuntu-desktop` |
| charlie | ubuntu-chromium | `http://example.com/desktop/charlie-ubuntu-chromium` |
| alice | ubuntu-desktop | `http://example.com/desktop/alice-ubuntu-desktop` |

**Note**: Same user can have multiple desktops of different types simultaneously!

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         User Browser                          │
│  http://example.com/desktop/alice-ubuntu-vscode              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             │ HTTP/WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (Optional)                          │
│                    Port 80/443                                │
│  - SSL/TLS Termination                                       │
│  - WebSocket Support                                         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             │ Forward to Flask
                             ▼
┌─────────────────────────────────────────────────────────────┐
│               Flask Application                               │
│               Port 5006                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Proxy Route: /desktop/<proxy_path>                  │   │
│  │  - Lookup container by proxy_path in database        │   │
│  │  - Forward to localhost:{host_port}                  │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Container A    │ │  Container B    │ │  Container C    │
│  localhost:7001 │ │  localhost:7002 │ │  localhost:7003 │
│  alice-ubuntu-  │ │  bob-ubuntu-    │ │  charlie-ubuntu-│
│  vscode         │ │  desktop        │ │  chromium       │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Common Scenarios

### Scenario 1: Single User, Multiple Desktops
**Alice** wants to use both VSCode and regular desktop:
- Starts VSCode: `http://example.com/desktop/alice-ubuntu-vscode`
- Starts Desktop: `http://example.com/desktop/alice-ubuntu-desktop`
- Both run simultaneously on different ports (7001, 7002)

### Scenario 2: Multiple Users, Same Desktop Type
**Alice, Bob, Charlie** all want Ubuntu Desktop:
- Alice: `http://example.com/desktop/alice-ubuntu-desktop` (port 7001)
- Bob: `http://example.com/desktop/bob-ubuntu-desktop` (port 7002)
- Charlie: `http://example.com/desktop/charlie-ubuntu-desktop` (port 7003)
- All access simultaneously without conflicts

### Scenario 3: Remote Team
Multiple team members working from different locations:
- All access via same domain: `http://company.com/desktop/...`
- Each gets their own isolated container
- No port conflicts or localhost issues
- Clean URLs easy to bookmark and share

## Deployment Checklist

### Development/Testing
- [ ] Copy `.env.example` to `.env`
- [ ] Set `DOCKER_HOST_URL=localhost`
- [ ] Configure OAuth credentials
- [ ] Run `docker-compose up`
- [ ] Access via `http://localhost:5006/desktop/{username}-{type}`

### Production (Minimal)
- [ ] Set `DOCKER_HOST_URL` to your actual domain
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set strong `VNC_PASSWORD`
- [ ] Configure OAuth for production
- [ ] Run behind a firewall
- [ ] Access via `http://your-domain.com/desktop/{username}-{type}`

### Production (Recommended)
- [ ] All minimal items above, plus:
- [ ] Uncomment nginx service in `docker-compose.yml`
- [ ] Configure SSL certificates
- [ ] Update `nginx.conf` for HTTPS
- [ ] Set up firewall rules (allow 80/443, block 5006 and 7000-8000)
- [ ] Configure monitoring and logging
- [ ] Set up automated backups
- [ ] Access via `https://your-domain.com/desktop/{username}-{type}`

## Troubleshooting

### "Container not found" error
**Problem**: URL returns 404
**Solution**:
1. Check container is running: `docker ps | grep kasm`
2. Check database: proxy_path must match URL
3. Verify container status is 'running'

### WebSocket connection issues (black screen)
**Problem**: noVNC can't connect
**Solution**: Use nginx reverse proxy (Option 2 in PROXY_DEPLOYMENT.md)

### Multiple users can't connect
**Problem**: Only one user can access at a time
**Solution**: Check that each user has unique proxy_path in database

### "Cannot access from remote machine"
**Problem**: Works on localhost but not remotely
**Solution**:
1. Ensure `DOCKER_HOST_URL` is set to your public domain (not localhost)
2. Configure firewall to allow port 80/443
3. For production, use nginx reverse proxy

## Performance Tips

1. **Use nginx in production**: Better WebSocket handling and performance
2. **Monitor container ports**: Max ~1000 containers (7000-8000 range)
3. **Set up container cleanup**: Run cleanup script regularly
4. **Use PostgreSQL**: Better concurrency than SQLite
5. **Consider resource limits**: Set CPU/memory limits per container

## Security Best Practices

1. **Use HTTPS**: Always use SSL/TLS in production
2. **Block internal ports**: Firewall should block 5006 and 7000-8000
3. **Strong passwords**: Use strong VNC_PASSWORD
4. **Regular updates**: Keep Docker images and base system updated
5. **Monitor logs**: Watch for unusual access patterns
6. **Rate limiting**: Add rate limiting at nginx level
7. **Network isolation**: Consider network policies for containers

## Next Steps

- **Testing**: Try accessing with multiple users simultaneously
- **Production**: Enable nginx and configure SSL
- **Monitoring**: Set up logging and alerts
- **Backup**: Configure database backups
- **Scale**: Consider load balancing for high traffic

## Support

- Full Documentation: [PROXY_DEPLOYMENT.md](PROXY_DEPLOYMENT.md)
- Usage Examples: [USAGE.md](USAGE.md)
- General Info: [README.md](README.md)
- Issues: GitHub Issues

## Summary

✅ **What You Get:**
- Clean URLs for all users
- Multiple simultaneous users
- Works remotely (not localhost-only)
- Single entry point (port 80/443)
- Production-ready with nginx
- WebSocket support for noVNC

🎯 **Perfect For:**
- Remote teams needing desktop access
- Educational environments with multiple students
- Development environments for distributed teams
- Any scenario requiring isolated desktop instances
