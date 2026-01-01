# Database Restructure Summary

## What Changed

The database structure has been restructured to properly separate concerns and support role-based management:

### 🔄 **Renamed Tables**
- `desktop_types` → `desktop_images`

### ✨ **New Columns**

#### desktop_images (formerly desktop_types)
- `created_by` - Tracks which admin created the image
- `updated_at` - Last update timestamp

#### desktop_assignments
- `desktop_image_id` - Foreign key to desktop_images (replaces desktop_type_id)
- `group_id` - Foreign key to groups table (replaces group_name string)
- `assignment_folder_path` - Path for teacher-assigned folders (e.g., "assignments/math101")
- `assignment_folder_name` - Display name for the folder (e.g., "Math 101 Homework")
- `created_by` - Tracks which teacher created the assignment
- `updated_at` - Last update timestamp

#### containers
- `desktop_image_id` - Foreign key to desktop_images

### 🗑️ **Removed Columns**
- `desktop_assignments.desktop_type_id` → replaced by `desktop_image_id`
- `desktop_assignments.group_name` → replaced by `group_id` (proper foreign key)

---

## Role Capabilities

### 👨‍💼 **ADMIN**
- ✅ Create/edit/delete desktop images
- ✅ Enable/disable desktop images
- ✅ View all assignments
- ✅ Manage all aspects of the system

### 👨‍🏫 **TEACHER**
- ✅ View available desktop images
- ✅ Assign images to groups or individual users
- ✅ Specify assignment folders for organized content
- ✅ Manage their own assignments
- ❌ Cannot create or modify desktop images

### 👨‍🎓 **STUDENT/USER**
- ✅ View desktops assigned to them (directly or via group)
- ✅ View desktops with no assignments (available to all)
- ✅ Launch assigned desktops
- ✅ Access assignment folders in containers
- ❌ Cannot create assignments or manage images

---

## Folder Structure in Containers

Each container will have this folder structure:

```
/home/kasm-user/
├── Desktop/              # User's desktop
├── Documents/            # User's personal files
├── Downloads/            # Downloads folder
└── public/
    ├── shared/           # Shared folder (all users)
    └── assignments/      # Assignment folders
        ├── math101/      # Example: Teacher-assigned folder
        ├── physics/      # Example: Another assignment
        └── project_x/    # Example: Group project folder
```

---

## Migration Files Created

1. **SQL Migration:**
   - [`migrations/006_restructure_desktop_images_assignments.sql`](../migrations/006_restructure_desktop_images_assignments.sql)
   - Manual SQL script for reference

2. **Python Migration Script:**
   - [`scripts/migrate_006_desktop_restructure.py`](../scripts/migrate_006_desktop_restructure.py)
   - Automated migration with data preservation
   - Includes rollback capability
   - **Run this to migrate your database**

3. **Documentation:**
   - [`migrations/006_RESTRUCTURE_GUIDE.md`](../migrations/006_RESTRUCTURE_GUIDE.md)
   - Complete guide with examples and API changes

---

## How to Migrate

### ⚠️ Before Migration
1. **Backup your database!**
   ```bash
   pg_dump -U postgres -d iserv_remote_desktop > backup_before_migration.sql
   ```

2. **Stop the application**
   ```bash
   docker-compose down
   ```

### 🚀 Run Migration
```bash
cd /root/iserv-remote-desktop
python scripts/migrate_006_desktop_restructure.py
```

### ✅ After Migration
1. Review migration output for warnings
2. Update any API routes that reference old table names
3. Test admin and teacher functionality
4. Test student desktop access

---

## Example Usage

### Admin Creates Desktop Image
```python
from app.models.desktop_assignments import DesktopImage

image = DesktopImage(
    name='VS Code',
    docker_image='kasmweb/vs-code:1.16.0',
    description='Visual Studio Code IDE',
    icon='💻',
    enabled=True,
    created_by=admin_user.id
)
db.session.add(image)
db.session.commit()
```

### Teacher Creates Assignment with Folder
```python
from app.models.desktop_assignments import DesktopAssignment

assignment = DesktopAssignment(
    desktop_image_id=image.id,
    group_id=math_class_group.id,
    assignment_folder_path='assignments/math101',
    assignment_folder_name='Math 101 Homework',
    created_by=teacher_user.id
)
db.session.add(assignment)
db.session.commit()
```

### Student Checks Access
```python
user_group_ids = [g.id for g in current_user.groups]

has_access, assignment = DesktopAssignment.check_access(
    desktop_image_id=1,
    user_id=current_user.id,
    user_group_ids=user_group_ids
)

if has_access and assignment:
    print(f"Assignment folder: {assignment.assignment_folder_name}")
    print(f"Path: {assignment.assignment_folder_path}")
```

---

## Next Steps

1. ✅ **Run the migration script**
2. ⚠️ **Update API routes** - See [006_RESTRUCTURE_GUIDE.md](../migrations/006_RESTRUCTURE_GUIDE.md) for required endpoint changes
3. 🧪 **Test the new structure**
4. 📝 **Update frontend** to show assignment folders
5. 🔧 **Implement folder mounting** in container creation logic

---

## Questions?

Refer to the complete guide:
- [migrations/006_RESTRUCTURE_GUIDE.md](../migrations/006_RESTRUCTURE_GUIDE.md)

## Files Modified

- ✏️ [`backend/app/models/desktop_assignments.py`](../backend/app/models/desktop_assignments.py) - Complete restructure
- ✏️ [`backend/app/models/containers.py`](../backend/app/models/containers.py) - Added desktop_image_id reference

## Files Created

- 📄 [`migrations/006_restructure_desktop_images_assignments.sql`](../migrations/006_restructure_desktop_images_assignments.sql)
- 🐍 [`scripts/migrate_006_desktop_restructure.py`](../scripts/migrate_006_desktop_restructure.py)
- 📚 [`migrations/006_RESTRUCTURE_GUIDE.md`](../migrations/006_RESTRUCTURE_GUIDE.md)
- 📋 This summary document
