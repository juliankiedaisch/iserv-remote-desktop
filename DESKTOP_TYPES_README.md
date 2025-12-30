# Desktop Types & Permission Management

This feature allows administrators to control which Docker images are available and assign them to specific users or groups.

## Overview

The desktop types system provides:
- **Desktop Type Management**: Define available Docker images with names, descriptions, and icons
- **Group Assignments**: Assign desktop types to IServ groups (e.g., "lehrende", "lernende")
- **User Assignments**: Assign desktop types to individual users by user ID
- **Permission Control**: Restrict container creation based on assignments

## Database Schema

### `desktop_types` Table
Stores available desktop image configurations:
- `id`: Primary key
- `name`: Unique name (e.g., "VS Code", "Python Dev")
- `docker_image`: Docker image name (e.g., "kasmweb/vs-code:1.16.0")
- `description`: User-friendly description
- `icon`: Emoji icon for UI display
- `enabled`: Boolean to enable/disable the desktop type

### `desktop_assignments` Table
Links desktop types to users/groups:
- `id`: Primary key
- `desktop_type_id`: Foreign key to desktop_types
- `group_name`: IServ group name (e.g., "lehrende")
- `user_id`: Individual user ID (UUID from OAuth)
- **Constraint**: Must have either `group_name` OR `user_id` (not both)

## Permission Logic

The `DesktopAssignment.check_access()` method determines access:

1. **Direct User Assignment**: If user_id matches, access granted
2. **Group Assignment**: If any user group matches group_name, access granted
3. **No Assignments**: If desktop type has no assignments, available to ALL users

**Example**:
```python
# Check if user can access desktop type
has_access = DesktopAssignment.check_access(
    desktop_type_id=1,
    user_id='uuid-123',
    user_groups=['lehrende', 'lernende']
)
```

## API Endpoints

All endpoints require admin authentication via `X-Session-ID` header.

### Desktop Types

#### List Desktop Types
```http
GET /api/admin/desktops/types
```

Response:
```json
{
  "success": true,
  "desktop_types": [
    {
      "id": 1,
      "name": "VS Code",
      "docker_image": "kasmweb/vs-code:1.16.0",
      "description": "Development environment",
      "icon": "💻",
      "enabled": true,
      "assignment_count": 2,
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

#### Create Desktop Type
```http
POST /api/admin/desktops/types
Content-Type: application/json

{
  "name": "Python Dev",
  "docker_image": "kasmweb/python:1.16.0",
  "description": "Python development with Jupyter",
  "icon": "🐍",
  "enabled": true
}
```

#### Update Desktop Type
```http
PUT /api/admin/desktops/types/{id}
Content-Type: application/json

{
  "name": "Python Development",
  "enabled": false
}
```

#### Delete Desktop Type
```http
DELETE /api/admin/desktops/types/{id}
```
**Note**: Cascade deletes all assignments.

### Assignments

#### List Assignments
```http
GET /api/admin/desktops/types/{id}/assignments
```

Response:
```json
{
  "success": true,
  "assignments": [
    {
      "id": 1,
      "desktop_type_id": 1,
      "group_name": "lehrende",
      "user_id": null
    },
    {
      "id": 2,
      "desktop_type_id": 1,
      "group_name": null,
      "user_id": "uuid-123"
    }
  ]
}
```

#### Create Assignment
```http
POST /api/admin/desktops/types/{id}/assignments
Content-Type: application/json

# Group assignment
{
  "group_name": "lehrende"
}

# OR user assignment
{
  "user_id": "uuid-123"
}
```

#### Delete Assignment
```http
DELETE /api/admin/desktops/assignments/{id}
```

## Admin UI

Access the desktop types management interface at:
```
https://desktop.hub.mdg-hamburg.de/admin/desktop-types
```

Features:
- Visual card-based desktop type list
- Create/edit/delete desktop types
- Manage assignments per desktop type
- See assignment counts and status
- Enable/disable desktop types

## Setup

### 1. Run Database Migration

```bash
docker exec -i mdg-scratch_postgres_1 psql -U scratch4school -d scratch4school < migrations/004_add_desktop_assignments.sql
```

This creates:
- `desktop_types` table
- `desktop_assignments` table
- Default entries: "VS Code" and "Ubuntu Desktop"

### 2. Restart Flask App

The blueprint is already registered, just restart:
```bash
docker-compose restart app
```

### 3. Access Admin UI

1. Login as admin at `https://desktop.hub.mdg-hamburg.de`
2. Go to Admin Panel
3. Click "🖥️ Desktop Types" button
4. Start managing desktop types and assignments

## Usage Examples

### Example 1: Teachers-Only Desktop

Create a desktop type only accessible to teachers:

1. Create desktop type "Advanced Tools"
2. Add assignment: Group = "lehrende"
3. Result: Only users in "lehrende" group can create this container

### Example 2: Student Desktop with Restrictions

Create a desktop type for all students:

1. Create desktop type "Basic Desktop"
2. Add assignment: Group = "lernende"
3. Result: All students can use this desktop

### Example 3: Public Desktop

Create a desktop type available to everyone:

1. Create desktop type "Public Desktop"
2. Don't add any assignments
3. Result: All authenticated users can create this container

### Example 4: Personal Desktop

Create a desktop type for a specific user:

1. Create desktop type "Custom Environment"
2. Add assignment: User ID = "user-uuid-here"
3. Result: Only that specific user can access this desktop

## Integration with Container Creation

To enforce permissions, update container creation logic:

```python
from app.models.desktop_assignments import DesktopType, DesktopAssignment

@container_bp.route('/api/containers/create', methods=['POST'])
@require_session
def create_container():
    # Get user info
    user = User.get_by_id(session.user_id)
    desktop_type_name = request.json.get('desktop_type')
    
    # Get desktop type
    desktop_type = DesktopType.query.filter_by(
        name=desktop_type_name,
        enabled=True
    ).first()
    
    if not desktop_type:
        return jsonify({"error": "Desktop type not available"}), 404
    
    # Check permission
    if not DesktopAssignment.check_access(
        desktop_type.id,
        user.id,
        user.groups  # List of group names from OAuth
    ):
        return jsonify({"error": "Permission denied"}), 403
    
    # Proceed with container creation...
```

## Testing

Use the test script to verify the API:

```bash
# 1. Get your admin session ID from browser console:
#    localStorage.getItem('session_id')

# 2. Edit the test script and set SESSION_ID

# 3. Run tests
cd /root/iserv-remote-desktop
python scripts/test_desktop_types.py
```

## Troubleshooting

### Desktop types not showing in UI
- Check database migration ran successfully
- Verify Flask app restarted after adding blueprint
- Check browser console for API errors
- Verify admin session is valid

### Permission checks not working
- Ensure user groups are properly set in User model
- Check `check_access()` logic matches your requirements
- Verify assignments exist in database

### Assignment constraints violated
- Each assignment must have EITHER group_name OR user_id
- Cannot have both fields set
- Cannot have both fields null

## Future Enhancements

Potential improvements:
- [ ] Container usage statistics per desktop type
- [ ] Desktop type categories/tags
- [ ] Resource limits per desktop type (CPU/RAM)
- [ ] Auto-cleanup policies per desktop type
- [ ] Desktop type templates/presets
- [ ] Bulk assignment operations
- [ ] Assignment import/export
