# Quick Reference: Desktop Management System

## Model Import Statements

```python
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.containers import Container
from app.models.users import User
from app.models.groups import Group
```

## Common Operations

### 1. Create Desktop Image (Admin Only)

```python
image = DesktopImage(
    name='VS Code',
    docker_image='kasmweb/vs-code:1.16.0',
    description='Visual Studio Code IDE',
    icon='💻',
    enabled=True,
    created_by=current_user.id  # Admin user ID
)
db.session.add(image)
db.session.commit()
```

### 2. Create Group Assignment (Teacher)

```python
assignment = DesktopAssignment(
    desktop_image_id=image.id,
    group_id=group.id,
    assignment_folder_path='assignments/math101',
    assignment_folder_name='Math 101 Homework',
    created_by=current_user.id  # Teacher user ID
)
db.session.add(assignment)
db.session.commit()
```

### 3. Create User Assignment (Teacher)

```python
assignment = DesktopAssignment(
    desktop_image_id=image.id,
    user_id=student.id,
    assignment_folder_path='assignments/special_project',
    assignment_folder_name='Special Project',
    created_by=current_user.id  # Teacher user ID
)
db.session.add(assignment)
db.session.commit()
```

### 4. Check User Access

```python
user_group_ids = [g.id for g in current_user.groups]

has_access, assignment = DesktopAssignment.check_access(
    desktop_image_id=image_id,
    user_id=current_user.id,
    user_group_ids=user_group_ids
)

if has_access:
    if assignment:
        print(f"Access via assignment: {assignment.to_dict()}")
        if assignment.assignment_folder_path:
            print(f"Folder: {assignment.assignment_folder_name}")
    else:
        print("Access via open desktop (no assignments)")
else:
    print("Access denied")
```

### 5. Get User's Available Desktops

```python
user_group_ids = [g.id for g in current_user.groups]

# Get assigned desktops
assignments = DesktopAssignment.get_user_assignments(
    user_id=current_user.id,
    user_group_ids=user_group_ids
)

# Get images with no assignments (available to all)
all_images = DesktopImage.query.filter_by(enabled=True).all()
assigned_image_ids = {a.desktop_image_id for a in DesktopAssignment.query.all()}
open_images = [img for img in all_images if img.id not in assigned_image_ids]

# Combine
available_images = []
for assignment in assignments:
    if assignment.desktop_image.enabled:
        available_images.append(assignment.desktop_image)
available_images.extend(open_images)

# Remove duplicates
available_images = list({img.id: img for img in available_images}.values())
```

### 6. Get Teacher's Assignments

```python
my_assignments = DesktopAssignment.get_by_teacher(current_user.id)

for assignment in my_assignments:
    data = assignment.to_dict(include_relations=True)
    print(f"Image: {data['desktop_image']['name']}")
    if data.get('group'):
        print(f"Assigned to group: {data['group']['name']}")
    if data.get('assigned_user'):
        print(f"Assigned to user: {data['assigned_user']['username']}")
    if data.get('assignment_folder_name'):
        print(f"Folder: {data['assignment_folder_name']}")
```

### 7. List All Desktop Images (Admin/Teacher)

```python
# All images
images = DesktopImage.query.all()

# Only enabled images
enabled_images = DesktopImage.query.filter_by(enabled=True).all()

# With assignment counts
for image in images:
    assignment_count = DesktopAssignment.query.filter_by(
        desktop_image_id=image.id
    ).count()
    print(f"{image.name}: {assignment_count} assignments")
```

### 8. Create Container with Image Reference

```python
container = Container(
    user_id=current_user.id,
    session_id=session.id,
    desktop_image_id=image.id,
    container_name=f"user-{current_user.username}-{image.name.lower()}",
    image_name=image.docker_image,
    status='creating'
)
db.session.add(container)
db.session.commit()

# Start container with Docker
docker_container = docker_client.containers.run(
    image.docker_image,
    name=container.container_name,
    # ... other Docker options
)

container.container_id = docker_container.id
container.status = 'running'
db.session.commit()
```

### 9. Update Desktop Image (Admin)

```python
image = DesktopImage.query.get(image_id)
image.name = 'VS Code Pro'
image.description = 'Updated description'
image.enabled = False
# updated_at is automatically updated
db.session.commit()
```

### 10. Delete Assignment (Teacher/Admin)

```python
assignment = DesktopAssignment.query.get(assignment_id)

# Teachers can only delete their own
if current_user.is_teacher and assignment.created_by != current_user.id:
    raise PermissionError("Cannot delete another teacher's assignment")

db.session.delete(assignment)
db.session.commit()
```

## API Route Examples

### Admin Routes (require ADMIN role)

```python
@admin_bp.route('/desktop-images', methods=['POST'])
@require_role('admin')
def create_desktop_image():
    data = request.json
    image = DesktopImage(
        name=data['name'],
        docker_image=data['docker_image'],
        description=data.get('description'),
        icon=data.get('icon'),
        enabled=data.get('enabled', True),
        created_by=current_user.id
    )
    db.session.add(image)
    db.session.commit()
    return jsonify(image.to_dict()), 201

@admin_bp.route('/desktop-images/<int:image_id>', methods=['PUT'])
@require_role('admin')
def update_desktop_image(image_id):
    image = DesktopImage.query.get_or_404(image_id)
    data = request.json
    
    if 'name' in data:
        image.name = data['name']
    if 'docker_image' in data:
        image.docker_image = data['docker_image']
    if 'description' in data:
        image.description = data['description']
    if 'icon' in data:
        image.icon = data['icon']
    if 'enabled' in data:
        image.enabled = data['enabled']
    
    db.session.commit()
    return jsonify(image.to_dict())

@admin_bp.route('/desktop-images/<int:image_id>', methods=['DELETE'])
@require_role('admin')
def delete_desktop_image(image_id):
    image = DesktopImage.query.get_or_404(image_id)
    db.session.delete(image)  # Cascades to assignments
    db.session.commit()
    return '', 204
```

### Teacher Routes (require TEACHER or ADMIN role)

```python
@teacher_bp.route('/assignments', methods=['POST'])
@require_role(['teacher', 'admin'])
def create_assignment():
    data = request.json
    
    # Validate: either group_id or user_id, not both
    if not data.get('group_id') and not data.get('user_id'):
        return jsonify({'error': 'Must specify group_id or user_id'}), 400
    if data.get('group_id') and data.get('user_id'):
        return jsonify({'error': 'Cannot specify both group_id and user_id'}), 400
    
    assignment = DesktopAssignment(
        desktop_image_id=data['desktop_image_id'],
        group_id=data.get('group_id'),
        user_id=data.get('user_id'),
        assignment_folder_path=data.get('assignment_folder_path'),
        assignment_folder_name=data.get('assignment_folder_name'),
        created_by=current_user.id
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify(assignment.to_dict(include_relations=True)), 201

@teacher_bp.route('/assignments/<int:assignment_id>', methods=['PUT'])
@require_role(['teacher', 'admin'])
def update_assignment(assignment_id):
    assignment = DesktopAssignment.query.get_or_404(assignment_id)
    
    # Teachers can only edit their own
    if current_user.is_teacher and assignment.created_by != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    if 'assignment_folder_path' in data:
        assignment.assignment_folder_path = data['assignment_folder_path']
    if 'assignment_folder_name' in data:
        assignment.assignment_folder_name = data['assignment_folder_name']
    
    db.session.commit()
    return jsonify(assignment.to_dict(include_relations=True))

@teacher_bp.route('/assignments', methods=['GET'])
@require_role(['teacher', 'admin'])
def list_assignments():
    if current_user.is_admin:
        # Admins see all
        assignments = DesktopAssignment.query.all()
    else:
        # Teachers see only their own
        assignments = DesktopAssignment.get_by_teacher(current_user.id)
    
    return jsonify([a.to_dict(include_relations=True) for a in assignments])
```

### User Routes

```python
@user_bp.route('/desktops', methods=['GET'])
@require_auth
def list_available_desktops():
    user_group_ids = [g.id for g in current_user.groups]
    
    # Get all enabled images
    all_images = DesktopImage.query.filter_by(enabled=True).all()
    
    available = []
    for image in all_images:
        has_access, assignment = DesktopAssignment.check_access(
            desktop_image_id=image.id,
            user_id=current_user.id,
            user_group_ids=user_group_ids
        )
        
        if has_access:
            image_data = image.to_dict()
            if assignment:
                image_data['assignment'] = {
                    'folder_path': assignment.assignment_folder_path,
                    'folder_name': assignment.assignment_folder_name
                }
            available.append(image_data)
    
    return jsonify(available)

@user_bp.route('/desktops/<int:image_id>/launch', methods=['POST'])
@require_auth
def launch_desktop(image_id):
    user_group_ids = [g.id for g in current_user.groups]
    
    # Check access
    has_access, assignment = DesktopAssignment.check_access(
        desktop_image_id=image_id,
        user_id=current_user.id,
        user_group_ids=user_group_ids
    )
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403
    
    image = DesktopImage.query.get_or_404(image_id)
    
    # Create container
    container = Container(
        user_id=current_user.id,
        session_id=current_session.id,
        desktop_image_id=image.id,
        container_name=f"user-{current_user.id}-{image.id}",
        image_name=image.docker_image,
        status='creating'
    )
    db.session.add(container)
    db.session.commit()
    
    # Start Docker container (implement your logic here)
    # If assignment has folder, mount it
    if assignment and assignment.assignment_folder_path:
        # Mount the assignment folder
        pass
    
    return jsonify(container.to_dict()), 201
```

## Validation Helpers

```python
def validate_folder_path(path):
    """Validate assignment folder path"""
    if not path:
        return True
    
    # Prevent directory traversal
    if '..' in path or path.startswith('/'):
        raise ValueError('Invalid folder path')
    
    # Ensure it's under assignments/
    if not path.startswith('assignments/'):
        path = f'assignments/{path}'
    
    return path

def can_edit_assignment(user, assignment):
    """Check if user can edit an assignment"""
    if user.is_admin:
        return True
    if user.is_teacher and assignment.created_by == user.id:
        return True
    return False

def can_delete_image(user, image):
    """Check if user can delete an image"""
    return user.is_admin
```

## Testing Queries

```python
# Check database state
print("Desktop Images:", DesktopImage.query.count())
print("Assignments:", DesktopAssignment.query.count())
print("Containers:", Container.query.count())

# Find orphaned assignments (no valid image)
orphaned = DesktopAssignment.query.filter(
    ~DesktopAssignment.desktop_image_id.in_(
        db.session.query(DesktopImage.id)
    )
).all()
print("Orphaned assignments:", len(orphaned))

# Find images with no assignments (open to all)
assigned_images = db.session.query(
    DesktopAssignment.desktop_image_id.distinct()
).all()
assigned_ids = [img[0] for img in assigned_images]
open_images = DesktopImage.query.filter(
    ~DesktopImage.id.in_(assigned_ids)
).all()
print("Open images:", [img.name for img in open_images])
```

## Common Mistakes to Avoid

❌ **Don't** set both group_id and user_id
```python
# WRONG
assignment = DesktopAssignment(
    group_id=1,
    user_id='user-123',  # Both set - will fail constraint
    ...
)
```

✅ **Do** set only one
```python
# RIGHT - Group assignment
assignment = DesktopAssignment(
    group_id=1,
    user_id=None,
    ...
)

# RIGHT - User assignment
assignment = DesktopAssignment(
    group_id=None,
    user_id='user-123',
    ...
)
```

❌ **Don't** use group_name (old field)
```python
# WRONG - Old structure
assignment.group_name = 'math_class'
```

✅ **Do** use group_id
```python
# RIGHT - New structure
group = Group.query.filter_by(name='math_class').first()
assignment.group_id = group.id
```

❌ **Don't** create assignments without checking role
```python
# WRONG - No role check
assignment = DesktopAssignment(created_by=any_user.id)
```

✅ **Do** verify user is teacher or admin
```python
# RIGHT - Check role first
if current_user.is_teacher or current_user.is_admin:
    assignment = DesktopAssignment(created_by=current_user.id, ...)
```
