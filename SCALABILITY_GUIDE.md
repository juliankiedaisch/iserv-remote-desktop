# Scalability Guide for 50-100 Concurrent Users

This document outlines the architecture changes and recommendations for supporting 50-100 concurrent users accessing the Remote Desktop service.

## Architecture Overview

### Frontend-Backend Separation

The application has been migrated to a separated architecture:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  React Frontend │────▶│  Flask Backend  │────▶│ Docker Host     │
│  (Static files) │     │  (API + WS)     │     │ (Containers)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │
         │    WebSocket (WS)     │
         └───────────────────────┘
```

### Real-time Updates

The application now uses Socket.IO for real-time updates:

- **Container status updates**: Broadcasted to relevant users
- **Admin notifications**: All container events sent to admin room
- **User-specific events**: Targeted to individual user rooms

## Bottleneck Analysis & Solutions

### 1. Database Connections

**Potential Issue**: With 50-100 users, concurrent database connections could exhaust the pool.

**Current Configuration** (optimized):
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,           # Base connections
    'pool_recycle': 3600,      # Recycle connections hourly
    'pool_pre_ping': True,     # Check connection health
    'max_overflow': 40         # Allow 40 additional connections
}
```

**Capacity**: Up to 60 concurrent database connections (20 base + 40 overflow).

**Recommendations**:
- For 100+ users, increase `pool_size` to 30-40
- Use PostgreSQL for production (better connection handling than SQLite)
- Consider PgBouncer for connection pooling at scale

### 2. Container Creation Concurrency

**Potential Issue**: Multiple users creating containers simultaneously could cause:
- Port allocation conflicts
- Database race conditions
- Docker API throttling

**Solutions Implemented**:

1. **Port Allocation Lock**: Uses database-level locking with `with_for_update()`:
   ```python
   containers = Container.query.filter(
       Container.status == 'running',
       Container.host_port.isnot(None)
   ).with_for_update().all()
   ```

2. **Container Cleanup**: Automatic cleanup of orphaned containers before creation

3. **Conflict Resolution**: Checks and cleans up conflicting proxy paths

**Recommendations**:
- Increase port range (7000-9000) for 100+ containers
- Implement container creation queue for very high load
- Add rate limiting per user (e.g., max 3 containers per user)

### 3. Session Management

**Potential Issue**: High session validation load with 50-100 concurrent users.

**Current Implementation**:
- Session validation on every API request
- Token refresh support
- Database-backed sessions

**Recommendations**:
- Implement Redis-based session caching
- Add JWT token caching with short TTL
- Consider sticky sessions for load-balanced deployments

### 4. WebSocket Scalability

**Potential Issue**: Single-server WebSocket connections don't scale horizontally.

**Current Implementation**:
- Socket.IO with gevent async mode
- Room-based message routing

**Recommendations for Horizontal Scaling**:
```python
# Use Redis as message queue for multiple workers
from flask_socketio import SocketIO

socketio = SocketIO(
    app,
    message_queue='redis://localhost:6379',
    async_mode='gevent'
)
```

### 5. Docker API Throttling

**Potential Issue**: Docker daemon can become overwhelmed with rapid container operations.

**Recommendations**:
- Implement exponential backoff for Docker API calls
- Add container creation queue
- Monitor Docker daemon metrics
- Consider Docker Swarm or Kubernetes for orchestration

## Production Deployment Recommendations

### 1. Infrastructure

```yaml
# Recommended docker-compose for production
services:
  app:
    deploy:
      replicas: 2-4  # Multiple workers
      resources:
        limits:
          cpus: '2'
          memory: 2G
    
  postgres:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
  
  redis:  # Add for session/WS scaling
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
```

### 2. Gunicorn Configuration

```bash
# Production gunicorn config for 50-100 users
gunicorn \
    --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    --workers 4 \
    --worker-connections 1000 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 10000 \
    --max-requests-jitter 1000 \
    run:app
```

### 3. Nginx Configuration

```nginx
# Optimize for concurrent connections
events {
    worker_connections 4096;
    multi_accept on;
    use epoll;
}

http {
    keepalive_timeout 65;
    keepalive_requests 100;
    
    # Connection pooling to backend
    upstream backend {
        server app:5006;
        keepalive 32;
    }
    
    # WebSocket support
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }
}
```

### 4. Monitoring

Key metrics to monitor:
- Container count per status
- Database connection pool usage
- WebSocket active connections
- Docker daemon CPU/memory
- API response times (P95/P99)

Recommended tools:
- Prometheus + Grafana for metrics
- Sentry for error tracking
- Docker stats for container monitoring

## Capacity Planning

| Users | Containers | DB Pool | Workers | Memory | Port Range |
|-------|------------|---------|---------|--------|------------|
| 25    | 50         | 20+20   | 2       | 2GB    | 7000-7500  |
| 50    | 100        | 20+40   | 3-4     | 4GB    | 7000-8000  |
| 100   | 200        | 30+50   | 4-6     | 8GB    | 7000-9000  |
| 200+  | 400+       | 40+80   | 8+      | 16GB+  | 7000-10000 |

## API Rate Limiting (Recommended)

Add rate limiting for API endpoints:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@limiter.limit("5 per minute")
@container_bp.route('/container/start', methods=['POST'])
def start_container():
    ...
```

## Summary

The application is designed to handle 50-100 concurrent users with the following optimizations:

1. **Database**: Connection pooling with 60 connection capacity
2. **WebSocket**: Real-time updates with Socket.IO rooms
3. **Container Creation**: Database-level locking for port allocation
4. **Session Management**: Database-backed with row-level locking

For scaling beyond 100 users:
- Add Redis for session/WebSocket scaling
- Implement horizontal scaling with load balancer
- Consider container orchestration (Kubernetes)
- Add comprehensive monitoring
