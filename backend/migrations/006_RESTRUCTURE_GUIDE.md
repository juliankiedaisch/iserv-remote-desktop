# Database Restructure: Desktop Images and Assignments

## Overview

This document describes the restructuring of the desktop management system to properly separate image management (ADMIN role) from assignment management (TEACHER role), and to add folder assignment capabilities.

## Changes Summary

### Previous Structure
- **desktop_types** table: Mixed image definitions with access control
- **desktop_assignments** table: Simple access control using group names (strings)
- Limited role separation
- No folder assignment capability

### New Structure
- **desktop_images** table: Image definitions managed by ADMINs
- **desktop_assignments** table: Enhanced assignments created by TEACHERs with folder paths
- **containers** table: Updated to reference desktop_images
- Proper foreign key relationships
- Support for folder assignments

---

## Table Structures

### 1. DesktopImage (desktop_images)
**Purpose:** Store available desktop Docker images (managed by ADMIN only)

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| name | String(128) | Unique display name (e.g., "VS Code", "Ubuntu Desktop") |
| docker_image | String(256) | Docker image tag (e.g., "kasmweb/vs-code:1.16.0") |
| description | Text | Optional description |
| icon | String(10) | Optional emoji icon |
| enabled | Boolean | Whether image is available for use |
| created_by | String(128) | Foreign key to users.id (admin who created it) |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |

**Relationships:**
- `assignments` → DesktopAssignment (one-to-many)
- `containers` → Container (one-to-many)

---

### 2. DesktopAssignment (desktop_assignments)
**Purpose:** Store assignments of desktop images to users/groups (created by TEACHER)

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| desktop_image_id | Integer | Foreign key to desktop_images.id |
| group_id | Integer | Foreign key to groups.id (optional) |
| user_id | String(128) | Foreign key to users.id (optional) |
| assignment_folder_path | String(512) | Relative path for assignment folder (optional) |
| assignment_folder_name | String(128) | Display name for assignment folder (optional) |
| created_by | String(128) | Foreign key to users.id (teacher who created assignment) |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |

**Constraints:**
- Either `group_id` OR `user_id` must be set (but not both)
- If no assignments exist for an image, it's available to all users

**Relationships:**
- `desktop_image` → DesktopImage (many-to-one)
- `group` → Group (many-to-one)
- `assigned_user` → User (many-to-one)
- `teacher` → User (many-to-one, via created_by)

---

### 3. Container (containers) - Updated
**Purpose:** Store running container instances

**New columns:**
| Column | Type | Description |
|--------|------|-------------|
| desktop_image_id | Integer | Foreign key to desktop_images.id |

**Updated columns:**
| Column | Type | Description |
|--------|------|-------------|
| desktop_type | String(50) | Now legacy field (kept for backwards compatibility) |

---

## Role-Based Access

### ADMIN Role
- **Can manage desktop images:**
  - Create new desktop images
  - Edit existing desktop images
  - Enable/disable desktop images
  - Delete desktop images (will cascade delete assignments)

### TEACHER Role
- **Can create assignments:**
  - Assign desktop images to groups
  - Assign desktop images to individual users
  - Specify assignment folder paths for organized content delivery
  - View and manage their own created assignments
  
### STUDENT/USER Role
- **Can access assigned desktops:**
  - View desktop images assigned to them (directly or via group)
  - View desktop images with no assignments (available to all)
  - Launch containers from assigned images
  - Access assignment folders created by teachers

---

## Folder Structure

Each container will have access to the following folder structure:

```
/home/kasm-user/
├── Desktop/           # User's desktop
├── Documents/         # User's personal documents
├── Downloads/         # User's downloads
└── public/
    ├── shared/        # Shared folder (accessible by all users)
    └── assignments/   # Assignment folders (created by teachers)
        ├── math101/   # Example: Math 101 assignment
        ├── physics/   # Example: Physics assignment
        └── ...
```

### Assignment Folder Path Examples

When a teacher creates an assignment with folder path:
- `assignment_folder_path`: `"assignments/math101"`
- `assignment_folder_name`: `"Math 101 Homework"`

The system will:
1. Create the folder at `/home/kasm-user/public/assignments/math101/`
2. Set appropriate permissions for the assigned users/groups
3. Display as "Math 101 Homework" in the UI

---

## Model Methods

### DesktopImage

```python
# Convert to dictionary
image.to_dict()

# Example output:
{
    'id': 1,
    'name': 'VS Code',
    'docker_image': 'kasmweb/vs-code:1.16.0',
    'description': 'Visual Studio Code IDE',
    'icon': '💻',
    'enabled': True,
    'created_by': 'admin-user-id',
    'created_at': '2026-01-01T00:00:00+00:00',
    'updated_at': '2026-01-01T00:00:00+00:00'
}
```

### DesktopAssignment

```python
# Check if user has access to a desktop image
has_access, assignment = DesktopAssignment.check_access(
    desktop_image_id=1,
    user_id='user-uuid',
    user_group_ids=[1, 2, 3]
)

# Get all assignments for a user
assignments = DesktopAssignment.get_user_assignments(
    user_id='user-uuid',
    user_group_ids=[1, 2, 3]
)

# Get all assignments created by a teacher
teacher_assignments = DesktopAssignment.get_by_teacher('teacher-uuid')

# Convert to dictionary with relations
assignment.to_dict(include_relations=True)

# Example output:
{
    'id': 1,
    'desktop_image_id': 1,
    'group_id': 5,
    'user_id': None,
    'assignment_folder_path': 'assignments/math101',
    'assignment_folder_name': 'Math 101 Homework',
    'created_by': 'teacher-uuid',
    'created_at': '2026-01-01T00:00:00+00:00',
    'updated_at': '2026-01-01T00:00:00+00:00',
    'desktop_image': {...},
    'group': {'id': 5, 'name': 'Math Class'},
    'teacher': {'id': 'teacher-uuid', 'username': 'teacher1'}
}
```

### Container

```python
# Convert to dictionary (now includes desktop_image info)
container.to_dict()

# Example output:
{
    'id': 'container-uuid',
    'container_id': 'docker-container-id',
    'container_name': 'user-vscode-123',
    'desktop_type': 'vscode',  # Legacy field
    'desktop_image_id': 1,
    'status': 'running',
    'host_port': 8080,
    'proxy_path': '/desktop/user-vscode-123',
    'created_at': '2026-01-01T00:00:00+00:00',
    'started_at': '2026-01-01T00:00:00+00:00',
    'last_accessed': '2026-01-01T00:00:00+00:00',
    'desktop_image': {
        'id': 1,
        'name': 'VS Code',
        'icon': '💻'
    }
}
```

---

## Migration Guide

### Running the Migration

1. **Backup your database first!**
   ```bash
   # Example for PostgreSQL
   pg_dump -U postgres -d iserv_remote_desktop > backup_before_migration_006.sql
   ```

2. **Run the migration script:**
   ```bash
   cd /root/iserv-remote-desktop
   python scripts/migrate_006_desktop_restructure.py
   ```

3. **Review the output:**
   - Check for any warnings about unmapped groups
   - Verify that all assignments were migrated correctly
   - Check that created_by was set appropriately

### Post-Migration Tasks

1. **Review Desktop Images:**
   - Set `created_by` for existing images if needed
   - Review and update descriptions/icons

2. **Review Assignments:**
   - Check assignments that couldn't find matching groups
   - Recreate any missing assignments
   - Add folder paths to assignments as needed

3. **Test the System:**
   - Test admin image management
   - Test teacher assignment creation
   - Test student desktop access
   - Test folder assignments

### Rollback (if needed)

```bash
# Restore from backup
psql -U postgres -d iserv_remote_desktop < backup_before_migration_006.sql

# Or use the rollback option (limited)
python scripts/migrate_006_desktop_restructure.py --rollback
```

---

## API Changes Required

### Admin Endpoints (require ADMIN role)

```
POST   /api/admin/desktop-images          # Create new desktop image
GET    /api/admin/desktop-images          # List all desktop images
GET    /api/admin/desktop-images/:id      # Get desktop image details
PUT    /api/admin/desktop-images/:id      # Update desktop image
DELETE /api/admin/desktop-images/:id      # Delete desktop image
```

### Teacher Endpoints (require TEACHER or ADMIN role)

```
POST   /api/teacher/assignments            # Create assignment
GET    /api/teacher/assignments            # List teacher's assignments
GET    /api/teacher/assignments/:id        # Get assignment details
PUT    /api/teacher/assignments/:id        # Update assignment
DELETE /api/teacher/assignments/:id        # Delete assignment

GET    /api/teacher/desktop-images         # List available images for assignment
GET    /api/teacher/groups                 # List available groups
GET    /api/teacher/users                  # List users for direct assignment
```

### User Endpoints

```
GET    /api/desktops                       # List available desktops for current user
POST   /api/desktops/:id/launch            # Launch a desktop
GET    /api/desktops/assignments           # Get user's assignments with folder info
```

---

## Implementation Example

### Creating an Assignment as a Teacher

```python
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.groups import Group

# Get the desktop image
image = DesktopImage.query.filter_by(name='VS Code').first()

# Get the group
group = Group.query.filter_by(name='Math Class').first()

# Create assignment with folder
assignment = DesktopAssignment(
    desktop_image_id=image.id,
    group_id=group.id,
    assignment_folder_path='assignments/math101',
    assignment_folder_name='Math 101 Homework',
    created_by=current_user.id  # Teacher's user ID
)

db.session.add(assignment)
db.session.commit()
```

### Checking Access as a User

```python
# Get user's group IDs
user_group_ids = [g.id for g in current_user.groups]

# Check if user has access to an image
has_access, assignment = DesktopAssignment.check_access(
    desktop_image_id=image_id,
    user_id=current_user.id,
    user_group_ids=user_group_ids
)

if has_access:
    # Launch container
    if assignment and assignment.assignment_folder_path:
        # Mount the assignment folder
        mount_folder(assignment.assignment_folder_path)
```

---

## Testing Checklist

- [ ] Admin can create desktop images
- [ ] Admin can edit desktop images
- [ ] Admin can delete desktop images (cascades to assignments)
- [ ] Teacher can create group assignments
- [ ] Teacher can create user assignments
- [ ] Teacher can specify folder paths
- [ ] Teacher can only see/edit their own assignments
- [ ] Admin can see/edit all assignments
- [ ] Students can access assigned desktops
- [ ] Students can access desktops with no assignments
- [ ] Students cannot access restricted desktops
- [ ] Assignment folders are created in containers
- [ ] Folder permissions are correct
- [ ] Migration handles existing data correctly
- [ ] Foreign key cascades work correctly

---

## Future Enhancements

1. **Assignment Scheduling:**
   - Add start_date and end_date to assignments
   - Automatic activation/deactivation

2. **Resource Limits:**
   - Per-assignment resource limits (CPU, memory)
   - Usage tracking and quotas

3. **Templates:**
   - Save assignment configurations as templates
   - Quick assignment creation from templates

4. **Notifications:**
   - Notify users when assignments are created
   - Remind users of assignment deadlines

5. **Analytics:**
   - Track desktop usage per assignment
   - Generate reports for teachers

---

## Support

For questions or issues related to this migration:
1. Check the migration logs in the terminal output
2. Review this documentation
3. Contact the system administrator
