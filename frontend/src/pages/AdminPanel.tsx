import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { Container } from '../types';
import { apiService } from '../services/api';
import './AdminPanel.css';

export const AdminPanel: React.FC = () => {
  const { user, isAdmin, logout, loading: authLoading } = useAuth();
  const [containers, setContainers] = useState<Container[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadContainers = useCallback(async () => {
    try {
      const response = await apiService.getAllContainers();
      if (response.success) {
        setContainers(response.containers);
        setError(null);
      } else {
        setError(response.error || 'Failed to load containers');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load containers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      loadContainers();
      // Auto-refresh every 10 seconds
      const interval = setInterval(loadContainers, 10000);
      return () => clearInterval(interval);
    }
  }, [isAdmin, loadContainers]);

  const stats = useMemo(() => {
    const total = containers.length;
    const running = containers.filter(c => c.status === 'running').length;
    const users = new Set(containers.map(c => c.user_id)).size;
    return { total, running, users };
  }, [containers]);

  const handleStopContainer = async (containerId: string, containerName: string) => {
    if (!window.confirm(`Stop container "${containerName}"?`)) return;

    setActionLoading(true);
    try {
      const response = await apiService.stopAdminContainer(containerId);
      if (response.success) {
        setSuccessMessage('Container stopped successfully');
        await loadContainers();
      } else {
        setError(response.error || 'Failed to stop container');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to stop container');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveContainer = async (containerId: string, containerName: string) => {
    if (!window.confirm(`Remove container "${containerName}"? This action cannot be undone.`)) return;

    setActionLoading(true);
    try {
      const response = await apiService.removeAdminContainer(containerId);
      if (response.success) {
        setSuccessMessage('Container removed successfully');
        await loadContainers();
      } else {
        setError(response.error || 'Failed to remove container');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to remove container');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopAll = async () => {
    if (!window.confirm('Stop ALL running containers? This will affect all users!')) return;

    setActionLoading(true);
    try {
      const response = await apiService.stopAllContainers();
      if (response.success) {
        setSuccessMessage(`Successfully stopped ${response.stopped_count} container(s)`);
        await loadContainers();
      } else {
        setError(response.error || 'Failed to stop containers');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to stop all containers');
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  if (authLoading) {
    return (
      <div className="container">
        <Loading message="Checking session..." />
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="container">
      <header className="header">
        <h1>⚙️ Admin Panel</h1>
        <div className="user-info">
          <span className="username">{user?.username} (Admin)</span>
          <Link to="/admin/desktop-types" className="btn btn-primary">
            🖥️ Desktop Types
          </Link>
          <Link to="/" className="btn btn-secondary">
            ← Back to Desktops
          </Link>
          <button className="btn btn-secondary" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {error && (
        <Alert type="error" message={error} onDismiss={() => setError(null)} />
      )}
      {successMessage && (
        <Alert type="success" message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <div className="admin-container">
        <div className="admin-header">
          <h2>Container Management</h2>
          <div className="admin-actions">
            <button className="btn btn-primary" onClick={loadContainers} disabled={actionLoading}>
              🔄 Refresh
            </button>
            <button className="btn btn-danger" onClick={handleStopAll} disabled={actionLoading}>
              ⏹️ Stop All
            </button>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">Total Containers</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.running}</div>
            <div className="stat-label">Running</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.users}</div>
            <div className="stat-label">Active Users</div>
          </div>
        </div>

        {loading ? (
          <Loading message="Loading containers..." />
        ) : containers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📦</div>
            <p>No containers found</p>
          </div>
        ) : (
          <table className="container-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Container Name</th>
                <th>Status</th>
                <th>Port</th>
                <th>Created</th>
                <th>Last Accessed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {containers.map((container) => (
                <tr key={container.id}>
                  <td><strong>{container.username || 'Unknown'}</strong></td>
                  <td>{container.container_name}</td>
                  <td>
                    <span className={`status-badge ${container.status}`}>
                      {container.status.toUpperCase()}
                    </span>
                  </td>
                  <td>{container.host_port || 'N/A'}</td>
                  <td>{formatDate(container.created_at)}</td>
                  <td>{formatDate(container.last_accessed)}</td>
                  <td>
                    <div className="action-buttons">
                      {container.status === 'running' && (
                        <>
                          {container.url && (
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => window.open(container.url, '_blank')}
                            >
                              Open
                            </button>
                          )}
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => handleStopContainer(container.id, container.container_name)}
                            disabled={actionLoading}
                          >
                            Stop
                          </button>
                        </>
                      )}
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleRemoveContainer(container.id, container.container_name)}
                        disabled={actionLoading}
                      >
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

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

export default AdminPanel;
