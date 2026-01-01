# Implementation Checklist

This checklist will guide you through implementing the new database structure in your application.

## ✅ Phase 1: Database Migration (CRITICAL - Do First!)

- [ ] **Backup database**
  ```bash
  pg_dump -U postgres -d iserv_remote_desktop > backup_$(date +%Y%m%d).sql
  ```

- [ ] **Stop application**
  ```bash
  docker-compose down
  ```

- [ ] **Run migration script**
  ```bash
  python scripts/migrate_006_desktop_restructure.py
  ```

- [ ] **Verify migration**
  - [ ] Check that `desktop_types` was renamed to `desktop_images`
  - [ ] Check that `desktop_assignments` has new columns
  - [ ] Check that foreign keys are in place
  - [ ] Review any warnings from migration

- [ ] **Update model imports**
  - [ ] Search for `DesktopType` and replace with `DesktopImage`
  - [ ] Search for `desktop_type` and update to `desktop_image` where appropriate

---

## ✅ Phase 2: Update Existing Code

### Models (Already Updated ✓)
- [x] `desktop_assignments.py` - Restructured
- [x] `containers.py` - Added desktop_image_id reference

### Routes to Update

- [ ] **Admin Routes** (`admin_routes.py` or `desktop_admin_routes.py`)
  - [ ] Find references to `desktop_types` → change to `desktop_images`
  - [ ] Update query filters
  - [ ] Update JSON responses

- [ ] **Container Routes** (`container_routes.py`)
  - [ ] Update container creation to use `desktop_image_id`
  - [ ] Update access checks to use new `DesktopAssignment.check_access()`
  - [ ] Update to pass `user_group_ids` instead of `user_groups` (names)

- [ ] **Auth Routes** (if checking desktop access)
  - [ ] Update any desktop access logic

### Services to Update

- [ ] **Docker Manager** (`docker_manager.py`)
  - [ ] Update to accept `desktop_image_id` parameter
  - [ ] Update to mount assignment folders if specified
  - [ ] Add folder mounting logic:
    ```python
    if assignment_folder_path:
        mount_path = f"/host/path/{assignment_folder_path}"
        container_path = f"/home/kasm-user/public/{assignment_folder_path}"
        # Add volume mount
    ```

---

## ✅ Phase 3: Create New API Endpoints

### Admin Endpoints (New)

- [ ] **POST /api/admin/desktop-images**
  ```python
  # Create new desktop image
  # Requires: ADMIN role
  # Body: name, docker_image, description, icon, enabled
  ```

- [ ] **GET /api/admin/desktop-images**
  ```python
  # List all desktop images
  # Requires: ADMIN role
  # Returns: List of images with assignment counts
  ```

- [ ] **GET /api/admin/desktop-images/:id**
  ```python
  # Get desktop image details
  # Requires: ADMIN role
  # Returns: Image details + assignments
  ```

- [ ] **PUT /api/admin/desktop-images/:id**
  ```python
  # Update desktop image
  # Requires: ADMIN role
  # Body: name, docker_image, description, icon, enabled
  ```

- [ ] **DELETE /api/admin/desktop-images/:id**
  ```python
  # Delete desktop image (cascades to assignments)
  # Requires: ADMIN role
  ```

### Teacher Endpoints (New)

- [ ] **GET /api/teacher/desktop-images**
  ```python
  # List available images for assignment
  # Requires: TEACHER or ADMIN role
  # Returns: Enabled images only
  ```

- [ ] **GET /api/teacher/groups**
  ```python
  # List available groups for assignment
  # Requires: TEACHER or ADMIN role
  # Returns: All groups
  ```

- [ ] **GET /api/teacher/users**
  ```python
  # List users for direct assignment
  # Requires: TEACHER or ADMIN role
  # Optional: filter by group
  ```

- [ ] **POST /api/teacher/assignments**
  ```python
  # Create assignment
  # Requires: TEACHER or ADMIN role
  # Body: desktop_image_id, group_id OR user_id, 
  #       assignment_folder_path, assignment_folder_name
  # Validation: Ensure only one of group_id/user_id is set
  ```

- [ ] **GET /api/teacher/assignments**
  ```python
  # List teacher's assignments (or all if admin)
  # Requires: TEACHER or ADMIN role
  # Returns: Assignments with relations
  ```

- [ ] **GET /api/teacher/assignments/:id**
  ```python
  # Get assignment details
  # Requires: TEACHER or ADMIN role
  # Authorization: Teacher can only see their own
  ```

- [ ] **PUT /api/teacher/assignments/:id**
  ```python
  # Update assignment
  # Requires: TEACHER or ADMIN role
  # Authorization: Teacher can only edit their own
  # Body: assignment_folder_path, assignment_folder_name
  ```

- [ ] **DELETE /api/teacher/assignments/:id**
  ```python
  # Delete assignment
  # Requires: TEACHER or ADMIN role
  # Authorization: Teacher can only delete their own
  ```

### User Endpoints (Update)

- [ ] **GET /api/desktops**
  ```python
  # Update to use new check_access method
  # Pass user_group_ids (not names)
  # Include assignment folder info in response
  ```

- [ ] **POST /api/desktops/:id/launch**
  ```python
  # Update access check
  # Use desktop_image_id
  # Mount assignment folder if present
  ```

- [ ] **GET /api/desktops/assignments**
  ```python
  # New: Get user's assignments
  # Returns: Assignments with folder information
  ```

---

## ✅ Phase 4: Update Frontend

### Admin Panel

- [ ] **Desktop Images Management Page**
  - [ ] List all desktop images
  - [ ] Create/Edit/Delete desktop images
  - [ ] Show assignment count per image
  - [ ] Enable/disable images

- [ ] **Assignment Overview** (Admin only)
  - [ ] View all assignments
  - [ ] Filter by teacher, group, or image
  - [ ] Edit/delete any assignment

### Teacher Panel

- [ ] **Assignment Creation Page**
  - [ ] Select desktop image (dropdown)
  - [ ] Choose target: Group or User
  - [ ] Optional: Specify assignment folder
    - [ ] Path input (auto-prefix with "assignments/")
    - [ ] Display name input
  - [ ] Create button

- [ ] **My Assignments Page**
  - [ ] List teacher's assignments
  - [ ] Show image, target (group/user), and folder
  - [ ] Edit/delete buttons
  - [ ] Assignment statistics

### Student/User Panel

- [ ] **Desktop Launcher**
  - [ ] Update to show available desktops
  - [ ] Show assignment folder info (if applicable)
  - [ ] Launch button

- [ ] **My Assignments View**
  - [ ] Show desktops assigned to user
  - [ ] Show assignment folders
  - [ ] Quick launch buttons

---

## ✅ Phase 5: Docker Integration

### Container Creation

- [ ] **Update container creation logic**
  ```python
  def create_container(user, desktop_image_id, assignment=None):
      image = DesktopImage.query.get(desktop_image_id)
      
      volumes = {}
      
      # Standard mounts
      volumes['/host/home/user'] = '/home/kasm-user'
      volumes['/host/shared'] = '/home/kasm-user/public/shared'
      
      # Assignment folder mount
      if assignment and assignment.assignment_folder_path:
          host_path = f'/host/assignments/{assignment.assignment_folder_path}'
          container_path = f'/home/kasm-user/public/{assignment.assignment_folder_path}'
          volumes[host_path] = container_path
      
      # Create Docker container
      container = docker_client.containers.run(
          image.docker_image,
          volumes=volumes,
          ...
      )
      
      return container
  ```

- [ ] **Create assignment folder structure on host**
  ```python
  def ensure_assignment_folder(folder_path):
      full_path = f'/host/assignments/{folder_path}'
      os.makedirs(full_path, exist_ok=True)
      # Set permissions
      os.chmod(full_path, 0o755)
  ```

---

## ✅ Phase 6: Testing

### Unit Tests

- [ ] Test `DesktopImage` model
  - [ ] Create/read/update/delete
  - [ ] Relationships
  - [ ] to_dict() method

- [ ] Test `DesktopAssignment` model
  - [ ] Create group assignment
  - [ ] Create user assignment
  - [ ] check_access() method
  - [ ] get_user_assignments() method
  - [ ] get_by_teacher() method
  - [ ] Validation (group_id XOR user_id)

- [ ] Test `Container` model updates
  - [ ] desktop_image_id reference
  - [ ] to_dict() includes image info

### Integration Tests

- [ ] **Admin workflows**
  - [ ] Create desktop image → Success
  - [ ] Edit desktop image → Success
  - [ ] Delete desktop image → Cascades to assignments
  - [ ] Non-admin tries to create image → Denied

- [ ] **Teacher workflows**
  - [ ] Create group assignment → Success
  - [ ] Create user assignment → Success
  - [ ] Create assignment with folder → Success
  - [ ] Edit own assignment → Success
  - [ ] Try to edit another teacher's assignment → Denied
  - [ ] View own assignments only → Success
  - [ ] Try to create desktop image → Denied

- [ ] **Student workflows**
  - [ ] View assigned desktops → Success
  - [ ] View open desktops (no assignments) → Success
  - [ ] Launch assigned desktop → Success
  - [ ] Try to launch restricted desktop → Denied
  - [ ] Assignment folder appears in container → Success
  - [ ] Try to create assignment → Denied

### Manual Testing

- [ ] **Test as Admin**
  - [ ] Create 3 desktop images
  - [ ] Enable/disable images
  - [ ] View all assignments
  - [ ] Delete an image (check cascade)

- [ ] **Test as Teacher**
  - [ ] Create assignment for a group
  - [ ] Create assignment for specific user
  - [ ] Create assignment with folder path
  - [ ] Edit assignment
  - [ ] Delete assignment
  - [ ] Verify cannot edit other teacher's assignments

- [ ] **Test as Student**
  - [ ] See only assigned desktops
  - [ ] Launch desktop
  - [ ] Verify assignment folder exists in container
  - [ ] Check folder permissions
  - [ ] Verify cannot access restricted desktops

---

## ✅ Phase 7: Documentation

- [ ] Update API documentation
  - [ ] Document new endpoints
  - [ ] Update request/response examples
  - [ ] Document error codes

- [ ] Update user documentation
  - [ ] Admin guide for managing images
  - [ ] Teacher guide for creating assignments
  - [ ] Student guide for accessing desktops

- [ ] Update deployment guide
  - [ ] Migration instructions
  - [ ] Rollback procedures
  - [ ] Troubleshooting

---

## ✅ Phase 8: Deployment

- [ ] **Pre-deployment**
  - [ ] Review all changes
  - [ ] Run full test suite
  - [ ] Backup production database
  - [ ] Schedule maintenance window

- [ ] **Deployment**
  - [ ] Stop application
  - [ ] Run migration script
  - [ ] Verify migration success
  - [ ] Deploy updated code
  - [ ] Restart application
  - [ ] Monitor logs

- [ ] **Post-deployment**
  - [ ] Verify admin can create images
  - [ ] Verify teacher can create assignments
  - [ ] Verify students can access desktops
  - [ ] Check for any errors in logs
  - [ ] Monitor performance

- [ ] **Cleanup**
  - [ ] Remove old backup files (after verification)
  - [ ] Update status page
  - [ ] Notify users of new features

---

## 🚨 Rollback Plan

If something goes wrong:

1. **Stop application immediately**
   ```bash
   docker-compose down
   ```

2. **Restore database from backup**
   ```bash
   psql -U postgres -d iserv_remote_desktop < backup_YYYYMMDD.sql
   ```

3. **Revert code changes**
   ```bash
   git checkout <previous-commit>
   ```

4. **Restart application**
   ```bash
   docker-compose up -d
   ```

5. **Investigate and fix issues**

---

## 📝 Notes

### Migration Warnings to Address

After running migration, check for:
- Assignments with unmapped groups → Recreate manually
- Images without created_by → Set to appropriate admin
- Orphaned containers → Clean up or link to images

### Performance Considerations

- Indexes are created on frequently queried columns
- Use `include_relations=False` in to_dict() when not needed
- Cache desktop availability checks if necessary

### Security Considerations

- Validate folder paths to prevent directory traversal
- Ensure teachers can only manage their own assignments
- Verify role checks on all endpoints
- Sanitize Docker image names

---

## ✅ Completion Checklist

Final verification before marking as complete:

- [ ] All database migrations completed successfully
- [ ] All models updated and tested
- [ ] All API endpoints implemented
- [ ] All frontend pages updated
- [ ] Docker integration working
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Deployment successful
- [ ] No critical errors in logs
- [ ] Users can perform their roles successfully

---

## 🎉 Success Criteria

The implementation is successful when:

1. ✅ Admins can fully manage desktop images
2. ✅ Teachers can create and manage assignments
3. ✅ Students can access appropriate desktops
4. ✅ Assignment folders appear in containers
5. ✅ No data loss from migration
6. ✅ Performance is acceptable
7. ✅ No critical bugs reported

---

## 📞 Support Contacts

If you need help:
- Check [RESTRUCTURE_SUMMARY.md](RESTRUCTURE_SUMMARY.md)
- Check [006_RESTRUCTURE_GUIDE.md](migrations/006_RESTRUCTURE_GUIDE.md)
- Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- Review migration logs
- Check application logs
