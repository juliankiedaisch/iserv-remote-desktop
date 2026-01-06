import React, { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Header, Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import { User } from '../types';
import { apiService } from '../services/api';
import './UserManagement.css';

interface RoleChangeModalState {
  isOpen: boolean;
  user: User | null;
  newRole: string | null;
}

export const UserManagement: React.FC = () => {
  const { user, isAdmin, isTeacher, isOAuthAdmin, logout, loading: authLoading } = useAuth();
  const { themeData } = useTheme();
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [roleChangeModal, setRoleChangeModal] = useState<RoleChangeModalState>({
    isOpen: false,
    user: null,
    newRole: null
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');

  const loadUsers = useCallback(async () => {
    try {
      const response = await apiService.getAllUsers();
      if (response.success) {
        setUsers(response.users);
        setError(null);
      } else {
        setError(response.error || 'Failed to load users');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      loadUsers();
    }
  }, [isAdmin, loadUsers]);

  const handleRoleChange = (user: User, newRole: string | null) => {
    setRoleChangeModal({
      isOpen: true,
      user,
      newRole
    });
  };

  const confirmRoleChange = async () => {
    if (!roleChangeModal.user) return;

    setRoleChangeModal({ ...roleChangeModal, isOpen: false });
    setActionLoading(true);

    try {
      const response = await apiService.updateUserRole(
        roleChangeModal.user.id,
        roleChangeModal.newRole
      );
      
      if (response.success) {
        setSuccessMessage(
          roleChangeModal.newRole 
            ? `Successfully updated role for ${roleChangeModal.user.username}` 
            : `Successfully removed role override for ${roleChangeModal.user.username}`
        );
        await loadUsers();
      } else {
        setError(response.error || 'Failed to update user role');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to update user role');
    } finally {
      setActionLoading(false);
    }
  };

  const getRoleBadgeClass = (role: string) => {
    switch (role) {
      case 'admin':
        return 'role-badge role-admin';
      case 'teacher':
        return 'role-badge role-teacher';
      case 'student':
        return 'role-badge role-student';
      default:
        return 'role-badge';
    }
  };

  const filteredUsers = users.filter(u => {
    const matchesSearch = u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          u.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          u.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  if (authLoading) {
    return (
      <div className="container">
        <Loading message={t('common.checkingSession')} />
      </div>
    );
  }

  if (!isOAuthAdmin) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="container">
      <Header
        title="🖥️ MDG Remote Desktop"
        user={user}
        isAdmin={isAdmin}
        isTeacher={isTeacher}
        onLogout={logout}
        appName={themeData.app_name}
        appIcon={themeData.app_icon}
      />

      {error && (
        <Alert type="error" message={error} onDismiss={() => setError(null)} />
      )}
      {successMessage && (
        <Alert type="success" message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <div className="user-management-container">
        <div className="user-management-header">
          <h2>👥 User Management</h2>
          <div className="user-management-actions">
            <Link to="/admin" className="btn btn-secondary">
              ← Back to Admin Panel
            </Link>
            <button className="btn btn-primary" onClick={loadUsers} disabled={actionLoading}>
              🔄 Refresh
            </button>
          </div>
        </div>

        <div className="filters-section">
          <div className="filter-group">
            <label htmlFor="search">🔍 Search:</label>
            <input
              id="search"
              type="text"
              placeholder="Search by username, email, or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>
          <div className="filter-group">
            <label htmlFor="roleFilter">Filter by Role:</label>
            <select
              id="roleFilter"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="role-filter"
            >
              <option value="all">All Roles</option>
              <option value="admin">Admin</option>
              <option value="teacher">Teacher</option>
              <option value="student">Student</option>
            </select>
          </div>
        </div>

        <div className="stats-summary">
          <div className="stat-item">
            <strong>Total Users:</strong> {users.length}
          </div>
          <div className="stat-item">
            <strong>Filtered:</strong> {filteredUsers.length}
          </div>
        </div>

        {loading ? (
          <Loading message="Loading users..." />
        ) : filteredUsers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <p>No users found</p>
          </div>
        ) : (
          <table className="user-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Current Role</th>
                <th>OAuth Role</th>
                <th>Override Status</th>
                <th>Groups</th>
                <th>Assignments</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.username}</strong></td>
                  <td>{u.email || 'N/A'}</td>
                  <td>
                    <span className={getRoleBadgeClass(u.role)}>
                      {u.role.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    {u.oauth_role && (
                      <span className={getRoleBadgeClass(u.oauth_role)}>
                        {u.oauth_role.toUpperCase()}
                      </span>
                    )}
                  </td>
                  <td>
                    {u.role_override ? (
                      <span className="override-badge">
                        ⚠️ Overridden
                      </span>
                    ) : (
                      <span className="no-override-badge">
                        OAuth
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="groups-list">
                      {u.groups && u.groups.length > 0 ? (
                        u.groups.slice(0, 3).map((group, idx) => (
                          <span key={idx} className="group-badge" title={group.name}>
                            {group.name}
                          </span>
                        ))
                      ) : (
                        <span className="no-groups">No groups</span>
                      )}
                      {u.groups && u.groups.length > 3 && (
                        <span className="group-badge">+{u.groups.length - 3} more</span>
                      )}
                    </div>
                  </td>
                  <td>{u.assignment_count || 0}</td>
                  <td>
                    <div className="action-buttons">
                      <select
                        className="role-select"
                        value="current"
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value !== 'current') {
                            handleRoleChange(u, value === 'remove' ? null : value);
                          }
                        }}
                        disabled={actionLoading}
                      >
                        <option value="current">
                          Current: {u.role.toUpperCase()}
                        </option>
                        <option value="admin">Set to Admin</option>
                        <option value="teacher">Set to Teacher</option>
                        <option value="student">Set to Student</option>
                        {u.role_override && (
                          <option value="remove">Remove Override</option>
                        )}
                      </select>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Role Change Confirmation Modal */}
      {roleChangeModal.isOpen && (
        <div className="modal-overlay" onClick={() => setRoleChangeModal({ ...roleChangeModal, isOpen: false })}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Confirm Role Change</h3>
              <button 
                className="modal-close" 
                onClick={() => setRoleChangeModal({ ...roleChangeModal, isOpen: false })}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              {roleChangeModal.user && (
                <>
                  <p>
                    Are you sure you want to {roleChangeModal.newRole ? 'change' : 'remove the role override for'} user{' '}
                    <strong>{roleChangeModal.user.username}</strong>?
                  </p>
                  {roleChangeModal.newRole ? (
                    <p>
                      New role: <strong>{roleChangeModal.newRole.toUpperCase()}</strong>
                    </p>
                  ) : (
                    <p>
                      This will revert the role to the OAuth-based role:{' '}
                      <strong>{roleChangeModal.user.oauth_role?.toUpperCase()}</strong>
                    </p>
                  )}
                </>
              )}
            </div>
            <div className="modal-footer">
              <button 
                className="btn btn-secondary" 
                onClick={() => setRoleChangeModal({ ...roleChangeModal, isOpen: false })}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button 
                className="btn btn-primary"
                onClick={confirmRoleChange}
                disabled={actionLoading}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {actionLoading && (
        <div className="loading-overlay">
          <div className="loading-content">
            <Loading message="Processing..." />
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
