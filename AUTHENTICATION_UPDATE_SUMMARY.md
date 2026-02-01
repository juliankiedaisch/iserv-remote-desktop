# Backend Authentication Update Summary

## Overview
Changed authentication mechanism from external dashboard to internal backend endpoint with role-based access control.

## Changes Made

### 1. New Backend Endpoint

**File:** `backend/app/routes/apache_api_routes.py`

**New Endpoint:** `/api/container-access-check`

**Functionality:**
- Called by nginx via `auth_request` directive
- Validates session cookie from browser
- Extracts container proxy_path from subdomain (Host header)
- Checks access permissions based on:
  - Container ownership (user_id match)
  - User role (teacher or admin get access to all containers)
- Returns HTTP status codes:
  - 200: Access granted
  - 401: Not authenticated
  - 403: Access denied
  - 404: Container not found

**Access Control Logic:**
```python
# 1. Owner has access
if container.user_id == user.id:
    return '', 200

# 2. Teachers and admins have access to all containers
if user.is_admin or user.is_teacher:
    return '', 200

# 3. No access
return jsonify({"error": "Access denied"}), 403
```

### 2. Nginx Configuration Update

**File:** `nginx.conf.traefik`

**Changed:**
```nginx
# OLD: External dashboard authentication
location = /auth-check-internal {
    proxy_pass https://dashboard.hub.mdg-hamburg.de/approvals/check;
}

# NEW: Backend authentication with role checks
location = /auth-check-internal {
    proxy_pass http://172.22.0.27:5021/api/container-access-check;
    proxy_set_header Host $host;
    proxy_set_header Cookie $http_cookie;
}
```

### 3. Environment Variables

**File:** `.env.example`

**Removed:**
- `DASHBOARD_AUTH_URL` (no longer needed)

### 4. Tests

**New File:** `backend/tests/test_container_access_check.py`

**Tests:**
- Proxy path extraction from subdomains
- Cookie parsing logic
- Access control logic (owner, teacher, admin, student)

All tests passing ✓

### 5. Documentation Updates

**Files Updated:**
- `docs/TRAEFIK_ARCHITECTURE.md`
  - Updated authentication flow section
  - Added access control rules
  - Updated troubleshooting for backend auth
  
- `DEPLOYMENT_GUIDE.md`
  - Updated authentication failure troubleshooting
  - Added role-based access checks

## Benefits

### Security
- ✅ Authentication handled by backend (single source of truth)
- ✅ Centralized access control with role checks
- ✅ Session validation using existing OAuth infrastructure

### Flexibility
- ✅ Easy to extend with additional roles
- ✅ Backend can check database for ownership
- ✅ Teachers and admins can supervise/support all containers

### Maintainability
- ✅ No external dashboard dependency for container access
- ✅ All authentication logic in one place
- ✅ Uses existing user role system

## Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Request: https://test-desktop-user-xyz.hub...       │
│    Cookie: session_id=abc123                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Nginx (Proxy Server)                                     │
│    - Receives HTTPS request                                 │
│    - Executes auth_request /auth-check-internal            │
│    - Forwards: Cookie, Host, X-Original-URI                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Backend: /api/container-access-check                     │
│    ┌─────────────────────────────────────────┐             │
│    │ a) Parse session_id from cookies        │             │
│    │ b) Validate session in database         │             │
│    │ c) Check session not expired            │             │
│    └─────────────────────────────────────────┘             │
│    ┌─────────────────────────────────────────┐             │
│    │ d) Extract proxy_path from Host header  │             │
│    │    - test-desktop-user-xyz.hub... →     │             │
│    │      proxy_path = "user-xyz"            │             │
│    └─────────────────────────────────────────┘             │
│    ┌─────────────────────────────────────────┐             │
│    │ e) Find container by proxy_path         │             │
│    │    - Query: Container.proxy_path = ...  │             │
│    └─────────────────────────────────────────┘             │
│    ┌─────────────────────────────────────────┐             │
│    │ f) Check access permissions:            │             │
│    │    - Is user the container owner?       │             │
│    │    - Is user role='teacher'?            │             │
│    │    - Is user role='admin'?              │             │
│    └─────────────────────────────────────────┘             │
│                                                              │
│    Decision:                                                │
│    ✅ Owner/Teacher/Admin → Return 200 OK                  │
│    ❌ Other users → Return 403 Forbidden                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Nginx continues if 200 OK                                │
│    - Injects Basic Auth header for Kasm                     │
│    - Proxies to Traefik: http://172.22.0.28                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Traefik routes to container based on Host header         │
└─────────────────────────────────────────────────────────────┘
```

## Access Control Matrix

| User Role | Own Container | Other's Container |
|-----------|---------------|-------------------|
| Student   | ✅ Allow      | ❌ Deny          |
| Teacher   | ✅ Allow      | ✅ Allow         |
| Admin     | ✅ Allow      | ✅ Allow         |

## Testing

### Unit Tests
All tests pass ✓

```bash
cd backend
python tests/test_container_access_check.py
```

**Output:**
```
Test 1: Proxy path extraction from subdomain
  ✓ Extracted proxy_path from test-desktop-user-ubuntu-token123...
  ✓ Extracted proxy_path from test-audio-user-abc...
  ✓ Extracted proxy_path from custom-prefix-john-doe-xyz...

Test 2: Cookie parsing
  ✓ Parsed single cookie
  ✓ Parsed multiple cookies
  ✓ No session_id cookie

Test 3: Access control logic
  ✓ Owner has access
  ✓ Admin has access to other's container
  ✓ Teacher has access to other's container
  ✓ Student denied access to other's container

All tests passed! ✓
```

### Manual Testing

1. **Owner Access:**
   ```bash
   # Create container as user A
   # Access as user A → Should work ✅
   ```

2. **Teacher Access:**
   ```bash
   # Create container as user A (student)
   # Access as user B (teacher) → Should work ✅
   ```

3. **Admin Access:**
   ```bash
   # Create container as user A (student)
   # Access as user C (admin) → Should work ✅
   ```

4. **Student Access:**
   ```bash
   # Create container as user A
   # Access as user D (another student) → Should fail (403) ✅
   ```

## Migration Notes

### No Breaking Changes
- Existing containers continue to work
- No changes to container creation logic
- URL format unchanged
- Session management unchanged

### Deployment Steps
1. Deploy updated backend code
2. Update nginx.conf on proxy server
3. Reload nginx
4. Test authentication with different user roles

### Rollback
If needed, revert to previous nginx configuration that used dashboard authentication.

## Future Enhancements

Potential improvements:
- Add group-based access control (share containers with specific groups)
- Add temporary access tokens for sharing
- Add audit logging for container access attempts
- Add rate limiting for authentication endpoint

---

**Date:** 2026-02-01  
**Commit:** 81bac50  
**Status:** Complete ✅
