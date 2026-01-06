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
        setError(response.error || t('userManagement.failedToLoadUsers'));
      }
    } catch (err: any) {
      setError(err.message || t('userManagement.failedToLoadUsers'));
    } finally {
      setLoading(false);
    }
  }, [t]);

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
            ? t('userManagement.roleUpdated', { username: roleChangeModal.user.username })
            : t('userManagement.overrideRemoved', { username: roleChangeModal.user.username })
        );
        await loadUsers();
      } else {
        setError(response.error || t('userManagement.failedToUpdateRole'));
      }
    } catch (err: any) {
      setError(err.message || t('userManagement.failedToUpdateRole'));
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
          <h2>👥 {t('userManagement.title')}</h2>
          <div className="user-management-actions">
            <Link to="/admin" className="btn btn-secondary">
              {t('userManagement.backToAdmin')}
            </Link>
            <button className="btn btn-primary" onClick={loadUsers} disabled={actionLoading}>
              🔄 {t('common.refresh')}
            </button>
          </div>
        </div>

        <div className="filters-section">
          <div className="filter-group">
            <label htmlFor="search">🔍 {t('common.search')}:</label>
            <input
              id="search"
              type="text"
              placeholder={t('userManagement.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>
          <div className="filter-group">
            <label htmlFor="roleFilter">{t('userManagement.filterByRole')}:</label>
            <select
              id="roleFilter"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="role-filter"
            >
              <option value="all">{t('userManagement.allRoles')}</option>
              <option value="admin">Admin</option>
              <option value="teacher">Teacher</option>
              <option value="student">Student</option>
            </select>
          </div>
        </div>

        <div className="stats-summary">
          <div className="stat-item">
            <strong>{t('userManagement.totalUsers')}:</strong> {users.length}
          </div>
          <div className="stat-item">
            <strong>{t('userManagement.filtered')}:</strong> {filteredUsers.length}
          </div>
        </div>

        {loading ? (
          <Loading message={t('userManagement.loadingUsers')} />
        ) : filteredUsers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <p>{t('userManagement.noUsers')}</p>
          </div>
        ) : (
          <table className="user-table">
            <thead>
              <tr>
                <th>{t('userManagement.username')}</th>
                <th>{t('userManagement.email')}</th>
                <th>{t('userManagement.currentRole')}</th>
                <th>{t('userManagement.oauthRole')}</th>
                <th>{t('userManagement.overrideStatus')}</th>
                <th>{t('userManagement.groups')}</th>
                <th>{t('userManagement.assignments')}</th>
                <th>{t('userManagement.actions')}</th>
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
                        ⚠️ {t('userManagement.overridden')}
                      </span>
                    ) : (
                      <span className="no-override-badge">
                        {t('userManagement.oauthBased')}
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
                        <span className="no-groups">{t('userManagement.noGroups')}</span>
                      )}
                      {u.groups && u.groups.length > 3 && (
                        <span className="group-badge">{t('userManagement.moreGroups', { count: u.groups.length - 3 })}</span>
                      )}
                    </div>
                  </td>
                  <td>{u.assignment_count || 0}</td>
                  <td>
                    <div className="action-buttons">
                      {u.oauth_role === 'admin' ? (
                        <div className="protected-role" title={t('userManagement.protectedTooltip')}>
                          🔒 {t('userManagement.protected')}
                        </div>
                      ) : (
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
                            {t('userManagement.currentRolePrefix')}{u.role.toUpperCase()}
                          </option>
                          <option value="admin">{t('userManagement.setToAdmin')}</option>
                          <option value="teacher">{t('userManagement.setToTeacher')}</option>
                          <option value="student">{t('userManagement.setToStudent')}</option>
                          {u.role_override && (
                            <option value="remove">{t('userManagement.removeOverride')}</option>
                          )}
                        </select>
                      )}
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
              <h3>{t('userManagement.confirmRoleChange')}</h3>
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
                    {t('userManagement.roleChangeMessage', { 
                      action: roleChangeModal.newRole ? t('userManagement.roleChangeAction') : t('userManagement.removeOverrideAction')
                    })}{' '}
                    <strong>{roleChangeModal.user.username}</strong>?
                  </p>
                  {roleChangeModal.newRole ? (
                    <p>
                      {t('userManagement.newRole')}: <strong>{roleChangeModal.newRole.toUpperCase()}</strong>
                    </p>
                  ) : (
                    <p>
                      {t('userManagement.revertToOAuth')}:{' '}
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
                {t('common.cancel')}
              </button>
              <button 
                className="btn btn-primary"
                onClick={confirmRoleChange}
                disabled={actionLoading}
              >
                {t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {actionLoading && (
        <div className="loading-overlay">
          <div className="loading-content">
            <Loading message={t('userManagement.processing')} />
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
