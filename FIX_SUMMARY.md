# Fix for Duplicate Key Violations in Container Creation

## Problem Statement

When starting containers, two errors were occurring:

### Error 1: Database Constraint Violation
```
Error: Failed to start desktop: (psycopg2.errors.UniqueViolation) 
duplicate key value violates unique constraint "containers_proxy_path_key" 
DETAIL: Key (proxy_path)=(julian.kiedaisch-ubuntu-vscode) already exists.
```

### Error 2: Docker Container Name Conflict
```
Error: Failed to start desktop: 409 Client Error for 
http+docker://localhost/v1.41/containers/create?name=kasm-julian.kiedaisch-ubuntu-desktop-cfe02614: 
Conflict ("Conflict. The container name "/kasm-julian.kiedaisch-ubuntu-desktop-cfe02614" is already 
in use by container "80b9b32cda04...". You have to remove (or rename) that container to be able to 
reuse that name.")
```

## Root Cause Analysis

The original cleanup logic in `create_container()` only checked for existing containers by matching:
- `session_id`
- `user_id` 
- `desktop_type`

However, the unique identifiers used were:

1. **proxy_path**: Generated as `{username}-{desktop_type}`
   - Problem: This is the same across ALL sessions for the same user and desktop type
   - Example: `julian.kiedaisch-ubuntu-vscode` is always the same

2. **container_name**: Generated as `kasm-{username}-{desktop_type}-{session_id[:8]}`
   - Problem: Uses only the first 8 characters of session_id
   - Risk: Can have collisions across different sessions

## The Bug Scenario

1. User starts a container in session A
   - Creates DB record with proxy_path = `julian.kiedaisch-ubuntu-vscode`
   - Creates Docker container with name = `kasm-julian.kiedaisch-ubuntu-vscode-abc12345`

2. Session A ends or container stops/errors

3. User starts a new session B and tries to start the same desktop type
   - Generates same proxy_path = `julian.kiedaisch-ubuntu-vscode` (CONFLICT!)
   - May generate same container_name if session_id prefix matches (CONFLICT!)
   - The old cleanup logic only looked for session_id + user_id + desktop_type match
   - Since session_id is different, the old containers weren't found
   - Attempt to insert DB record fails due to unique constraint on proxy_path
   - Even if DB insert succeeded, Docker creation fails due to name conflict

## Solution Implemented

Added comprehensive cleanup logic that checks for conflicts by **proxy_path** and **container_name** before creating new containers:

### Changes Made to `app/services/docker_manager.py`:

1. **Added SQLAlchemy import**:
   ```python
   from sqlalchemy import or_
   ```

2. **Added conflict detection query**:
   ```python
   conflicting_containers = Container.query.filter(
       or_(
           Container.proxy_path == proxy_path,
           Container.container_name == container_name
       ),
       Container.user_id == user_id  # Only cleanup user's own containers
   ).all()
   ```

3. **Added cleanup loop for conflicting containers**:
   - Removes Docker containers (with force=True to handle running containers)
   - Removes database records
   - Logs all cleanup operations

4. **Added orphaned Docker container cleanup**:
   - Checks if a Docker container with the target name exists but isn't in the database
   - Removes it before attempting to create the new container

## How It Fixes Both Errors

### Error 1 Fix (proxy_path constraint):
- Before creating a new container, query for any existing containers with the same `proxy_path`
- Delete those containers from both Docker and the database
- Now the proxy_path is free and the new container can be inserted

### Error 2 Fix (container_name conflict):
- Before creating a new container, query for any existing containers with the same `container_name`
- Delete those containers from both Docker and the database
- Also check Docker directly for orphaned containers with the same name
- Now the container_name is free and Docker can create the new container

## Safety Considerations

1. **User Isolation**: Only cleans up containers belonging to the same user (`Container.user_id == user_id`)
2. **Force Removal**: Uses `force=True` when removing Docker containers to handle running containers
3. **Error Handling**: Continues cleanup even if individual Docker container removal fails
4. **Logging**: Comprehensive logging of all cleanup operations for debugging

## Testing

Created comprehensive test suite in `scripts/test_duplicate_cleanup.py` that validates:
1. Cleanup of containers with duplicate proxy_path
2. Cleanup of containers with duplicate container_name
3. Cleanup of multiple leftover containers from different sessions

## Backwards Compatibility

The fix is backwards compatible:
- Existing cleanup logic for session-based containers is preserved
- New conflict detection is additive - runs after existing cleanup
- No changes to database schema or container generation logic
- Only adds additional cleanup before container creation

## Code Quality

- No syntax errors (verified with py_compile)
- Proper imports (SQLAlchemy or_)
- Follows existing code patterns
- Includes comprehensive logging
- Minimal changes to existing code
