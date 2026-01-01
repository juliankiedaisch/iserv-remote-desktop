# Database Schema Diagram

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Database Structure                               │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐                    ┌──────────────────┐
│     Users        │                    │     Groups       │
├──────────────────┤                    ├──────────────────┤
│ id (PK)          │                    │ id (PK)          │
│ username         │                    │ name             │
│ email            │                    │ external_id      │
│ role ───────────┼─────────┐          │ description      │
│ created_at       │  ADMIN  │          └──────────────────┘
│ last_login       │ TEACHER │                   │
│ user_data        │ STUDENT │                   │
└──────────────────┘         │                   │
        │                    │                   │
        │ created_by         │                   │
        │                    │                   │
        ▼                    │                   │
┌──────────────────┐         │                   │
│ DesktopImage     │         │                   │
├──────────────────┤         │                   │
│ id (PK)          │         │                   │
│ name             │         │                   │
│ docker_image     │◄────────┤ Managed           │
│ description      │         │ by ADMIN          │
│ icon             │         │                   │
│ enabled          │         │                   │
│ created_by (FK) ─┘         │                   │
│ created_at       │         │                   │
│ updated_at       │         │                   │
└──────────────────┘         │                   │
        │                    │                   │
        │ desktop_image_id   │                   │
        │                    │                   │
        ▼                    │                   │
┌──────────────────┐         │                   │
│DesktopAssignment │         │                   │
├──────────────────┤         │                   │
│ id (PK)          │         │                   │
│ desktop_image_id │◄────────┤ Created           │
│ group_id (FK) ───┼─────────┼───────────────────┘
│ user_id (FK)     │         │ by TEACHER
│ assignment_      │         │
│   folder_path    │         │
│ assignment_      │         │
│   folder_name    │         │
│ created_by (FK) ─┼─────────┘
│ created_at       │
│ updated_at       │
└──────────────────┘
        │
        │ Determines access
        │
        ▼
┌──────────────────┐
│    Container     │
├──────────────────┤
│ id (PK)          │
│ user_id (FK)     │
│ session_id (FK)  │
│ desktop_image_id │◄─── Links to DesktopImage
│ container_id     │
│ container_name   │
│ image_name       │
│ status           │
│ host_port        │
│ proxy_path       │
│ created_at       │
│ started_at       │
│ stopped_at       │
│ last_accessed    │
└──────────────────┘
```

## Relationships

### One-to-Many
- **User** (ADMIN) → **DesktopImage** (created_by)
- **User** (TEACHER) → **DesktopAssignment** (created_by)
- **DesktopImage** → **DesktopAssignment** (desktop_image_id)
- **DesktopImage** → **Container** (desktop_image_id)
- **Group** → **DesktopAssignment** (group_id)
- **User** → **DesktopAssignment** (user_id)

### Many-to-Many
- **User** ↔ **Group** (through user_groups table)

## Access Control Flow

```
┌─────────────┐
│   Student   │
│   Logs In   │
└──────┬──────┘
       │
       │ 1. Get user_id and group_ids
       ▼
┌────────────────────────────────────┐
│  DesktopAssignment.check_access()  │
│  - Check direct user assignment    │
│  - Check group assignment          │
│  - Check if no assignments (open)  │
└──────┬─────────────────────────────┘
       │
       │ 2. Returns (has_access, assignment)
       ▼
┌──────────────────┐
│ Can Access?      │
├──────────────────┤
│ ✓ Yes → Launch  │
│ ✗ No → Deny     │
└──────────────────┘
       │
       │ 3. If assignment has folder_path
       ▼
┌────────────────────────────────────┐
│  Create Container                  │
│  - Use desktop_image.docker_image  │
│  - Mount assignment_folder_path    │
│  - Set permissions                 │
└────────────────────────────────────┘
```

## Folder Assignment Flow

```
┌────────────────┐
│    Teacher     │
│ Creates        │
│ Assignment     │
└────────┬───────┘
         │
         │ Assigns:
         │ - Desktop Image: "VS Code"
         │ - Group: "Math Class"
         │ - Folder: "assignments/math101"
         │ - Name: "Math 101 Homework"
         ▼
┌─────────────────────────────────────┐
│      DesktopAssignment Created      │
│  (stored in database)               │
└────────┬────────────────────────────┘
         │
         │ When student launches container:
         ▼
┌─────────────────────────────────────┐
│     Container File System           │
│                                     │
│  /home/kasm-user/                   │
│  ├── Desktop/                       │
│  ├── Documents/                     │
│  ├── Downloads/                     │
│  └── public/                        │
│      ├── shared/                    │
│      └── assignments/               │
│          └── math101/  ◄────────────┼── Mounted here
│              └── [assignment files] │
└─────────────────────────────────────┘
```

## Role Permissions Matrix

| Action                        | Admin | Teacher | Student |
|-------------------------------|-------|---------|---------|
| Create Desktop Image          | ✅    | ❌      | ❌      |
| Edit Desktop Image            | ✅    | ❌      | ❌      |
| Delete Desktop Image          | ✅    | ❌      | ❌      |
| View All Desktop Images       | ✅    | ✅      | ❌      |
| Create Assignment             | ✅    | ✅      | ❌      |
| Edit Own Assignment           | ✅    | ✅      | ❌      |
| Edit Any Assignment           | ✅    | ❌      | ❌      |
| Delete Own Assignment         | ✅    | ✅      | ❌      |
| Delete Any Assignment         | ✅    | ❌      | ❌      |
| View Own Assignments          | ✅    | ✅      | ✅      |
| View All Assignments          | ✅    | ❌      | ❌      |
| Set Assignment Folder         | ✅    | ✅      | ❌      |
| Launch Assigned Desktop       | ✅    | ✅      | ✅      |
| Access Assignment Folders     | ✅    | ✅      | ✅      |

## Data Validation Rules

### DesktopImage
- ✓ `name` must be unique
- ✓ `docker_image` is required
- ✓ `created_by` should reference valid admin user

### DesktopAssignment
- ✓ `desktop_image_id` must reference valid DesktopImage
- ✓ Either `group_id` OR `user_id` must be set (not both)
- ✓ `created_by` must reference valid user (teacher or admin)
- ✓ If `assignment_folder_path` is set, it should be validated
- ✓ `assignment_folder_path` should not contain `..` or absolute paths

### Container
- ✓ `desktop_image_id` should reference valid DesktopImage (optional)
- ✓ `user_id` must reference valid user
- ✓ `session_id` must reference valid session
- ✓ `container_name` must be unique

## Migration Impact

### Before Migration
```sql
-- Old structure
SELECT * FROM desktop_types;
-- id | name | docker_image | description | icon | enabled | created_at

SELECT * FROM desktop_assignments;
-- id | desktop_type_id | group_name | user_id | created_at
```

### After Migration
```sql
-- New structure
SELECT * FROM desktop_images;
-- id | name | docker_image | description | icon | enabled 
-- | created_by | created_at | updated_at

SELECT * FROM desktop_assignments;
-- id | desktop_image_id | group_id | user_id 
-- | assignment_folder_path | assignment_folder_name
-- | created_by | created_at | updated_at
```

## Example Queries

### Get all available desktops for a user
```python
user_group_ids = [g.id for g in user.groups]

# Get assignments
assignments = DesktopAssignment.get_user_assignments(
    user_id=user.id,
    user_group_ids=user_group_ids
)

# Get images with no assignments (open to all)
all_images = DesktopImage.query.filter_by(enabled=True).all()
assigned_image_ids = [a.desktop_image_id for a in DesktopAssignment.query.all()]
open_images = [img for img in all_images if img.id not in assigned_image_ids]
```

### Get all assignments created by a teacher
```python
teacher_assignments = DesktopAssignment.get_by_teacher(teacher.id)
```

### Check if user can access a specific image
```python
has_access, assignment = DesktopAssignment.check_access(
    desktop_image_id=image_id,
    user_id=user.id,
    user_group_ids=[g.id for g in user.groups]
)
```
