# User Management Feature - Testing Guide

## Overview
This guide explains how to test the new admin user management feature that allows admins to view all users and override their OAuth-based roles.

## Features Implemented

### Backend Changes
1. **User Model Updates** (`backend/app/models/users.py`)
   - Added `role_override` column to store admin-set role overrides
   - Added `get_oauth_role()` method to get the OAuth-based role
   - Updated `get_or_create()` to respect role overrides
   - Updated `to_dict()` to include `role_override` and `oauth_role` fields

2. **Database Migration** (`backend/migrations/009_add_role_override_column.sql`)
   - Adds `role_override` column to the `users` table
   - Column is nullable (NULL means no override)

3. **Admin API Endpoints** (`backend/app/routes/admin_routes.py`)
   - `GET /api/admin/users` - List all users with their groups and assignments
   - `PUT /api/admin/user/<user_id>/role` - Update a user's role override

4. **Internationalization** (`backend/app/i18n/__init__.py`)
   - Added messages: `user_not_found`, `user_role_updated`

### Frontend Changes
1. **Type Updates** (`frontend/src/types/index.ts`)
   - Updated `User` interface to include `role_override`, `oauth_role`, `assignment_count`, and `assignments`

2. **API Service** (`frontend/src/services/api.ts`)
   - Added `getAllUsers()` method
   - Added `updateUserRole(userId, role)` method

3. **User Management Page** (`frontend/src/pages/UserManagement.tsx`)
   - New page for admins to manage user roles
   - Features:
     - View all users with their current role, OAuth role, and override status
     - Search users by username, email, or ID
     - Filter users by role
     - Change user roles with confirmation modal
     - Remove role overrides to revert to OAuth roles
     - View user groups and assignment counts

4. **Admin Panel Update** (`frontend/src/pages/AdminPanel.tsx`)
   - Added link to User Management page

5. **Routing** (`frontend/src/App.tsx`)
   - Added route `/admin/users` for the User Management page

## Testing Instructions

### Prerequisites
1. Ensure PostgreSQL database is running
2. Ensure Docker daemon is accessible
3. Have OAuth configured with admin, teacher, and student groups

### Backend Testing

#### 1. Database Migration
```bash
# Start the backend (migrations run automatically on startup)
cd backend
python run.py
```

Check the logs for:
```
✓ Executed migration: 009_add_role_override_column.sql
```

#### 2. Test API Endpoints

**Test List Users Endpoint:**
```bash
# Get an admin session ID first by logging in
SESSION_ID="your-admin-session-id"

# List all users
curl -X GET "http://localhost:5021/api/admin/users" \
  -H "X-Session-ID: $SESSION_ID"
```

Expected response:
```json
{
  "success": true,
  "users": [
    {
      "id": "user-123",
      "username": "john.doe",
      "email": "john@example.com",
      "role": "student",
      "role_override": null,
      "oauth_role": "student",
      "groups": [...],
      "assignments": [...],
      "assignment_count": 2
    }
  ]
}
```

**Test Update User Role Endpoint:**
```bash
# Override a user's role to teacher
curl -X PUT "http://localhost:5021/api/admin/user/user-123/role" \
  -H "X-Session-ID: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"role": "teacher"}'
```

Expected response:
```json
{
  "success": true,
  "message": "User role updated successfully",
  "user": {
    "id": "user-123",
    "username": "john.doe",
    "role": "teacher",
    "role_override": "teacher",
    "oauth_role": "student"
  }
}
```

**Test Remove Role Override:**
```bash
# Remove the override (revert to OAuth role)
curl -X PUT "http://localhost:5021/api/admin/user/user-123/role" \
  -H "X-Session-ID: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"role": null}'
```

Expected response:
```json
{
  "success": true,
  "message": "User role updated successfully",
  "user": {
    "id": "user-123",
    "username": "john.doe",
    "role": "student",
    "role_override": null,
    "oauth_role": "student"
  }
}
```

### Frontend Testing

#### 1. Build Frontend
```bash
cd frontend
npm install
npm run build
```

Should complete without errors.

#### 2. Manual UI Testing

1. **Access User Management Page**
   - Log in as an admin user
   - Navigate to Admin Panel
   - Click "👥 User Management" button
   - Should see the user management page

2. **View User List**
   - Verify the page shows all users
   - Check that each user row displays:
     - Username
     - Email
     - Current Role (with colored badge)
     - OAuth Role (with colored badge)
     - Override Status (⚠️ Overridden or OAuth)
     - Groups (first 3 shown)
     - Assignment count
     - Role selection dropdown

3. **Test Search Functionality**
   - Type in the search box
   - Verify results filter by username, email, or ID
   - Clear search and verify all users return

4. **Test Role Filter**
   - Select "Admin" from role filter dropdown
   - Verify only admin users are shown
   - Try other roles
   - Select "All Roles" to reset

5. **Test Role Change**
   - Select a user
   - Choose a different role from the dropdown
   - Verify confirmation modal appears
   - Confirm the change
   - Verify success message appears
   - Verify the user's role badge updates
   - Verify "⚠️ Overridden" badge appears

6. **Test Remove Override**
   - For a user with an override, select "Remove Override"
   - Verify confirmation modal explains the revert
   - Confirm the action
   - Verify the override badge changes to "OAuth"
   - Verify the role reverts to OAuth role

7. **Test Refresh**
   - Click the "🔄 Refresh" button
   - Verify the user list reloads

### Role Override Behavior Testing

#### Scenario 1: User with OAuth Student Role
1. User logs in with OAuth groups indicating "student"
2. Check user role: should be "student"
3. Admin overrides role to "teacher"
4. User logs out and logs back in
5. Check user role: should still be "teacher" (override persists)

#### Scenario 2: Remove Override
1. User has role override set to "teacher"
2. OAuth groups indicate "student"
3. Admin removes override
4. Check user role: should be "student" (reverted to OAuth)

#### Scenario 3: OAuth Role Changes
1. User has role override set to "admin"
2. OAuth groups change from "student" to "teacher"
3. User logs in
4. Check user role: should still be "admin" (override takes precedence)
5. Check oauth_role: should show "teacher" (new OAuth role)

## Expected Behavior Summary

### Role Determination Logic
```
IF role_override IS NOT NULL:
    user.role = role_override
ELSE:
    user.role = determined from OAuth groups
```

### API Permissions
- Only admin users can access `/api/admin/users` and `/api/admin/user/<user_id>/role`
- Non-admin users receive 403 Forbidden

### Frontend Access
- Only admin users can access `/admin/users` page
- Non-admin users are redirected to home page

## Visual Reference

The User Management page should display:
- Header with "👥 User Management" title
- Back button and Refresh button
- Search input and role filter dropdown
- Stats summary showing total and filtered user counts
- Table with columns:
  - Username
  - Email
  - Current Role (colored badge: red=admin, yellow=teacher, green=student)
  - OAuth Role (colored badge)
  - Override Status (orange=overridden, gray=OAuth)
  - Groups (badges, max 3 visible)
  - Assignments (count)
  - Actions (role selection dropdown)

## Troubleshooting

### Backend Issues
- **Migration doesn't run**: Check PostgreSQL connection and logs
- **403 Forbidden on API calls**: Verify user has admin role
- **500 Internal Server Error**: Check backend logs for details

### Frontend Issues
- **Build fails**: Run `npm install` again, check for TypeScript errors
- **Page doesn't load**: Check browser console for errors
- **API calls fail**: Verify backend is running and session is valid

## Security Considerations

1. **Role Override Persistence**: Role overrides persist across logins until explicitly removed
2. **Admin Only**: Only admin users can view and modify role overrides
3. **Audit Trail**: All role changes are logged in backend logs with admin username
4. **OAuth Safety**: Original OAuth role is preserved and shown for reference
5. **Validation**: Only valid roles (admin, teacher, student, null) are accepted

## Database Schema Changes

```sql
-- New column in users table
ALTER TABLE users ADD COLUMN role_override VARCHAR(50);
```

The `role_override` column:
- Is nullable (NULL means no override)
- Accepts values: 'admin', 'teacher', 'student', or NULL
- When set, takes precedence over OAuth-based role
- Can be viewed in the user management UI with ⚠️ indicator
