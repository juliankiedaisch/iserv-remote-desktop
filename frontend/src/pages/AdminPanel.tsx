import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { Container } from '../types';
import { apiService } from '../services/api';
import './AdminPanel.css';

interface ConfirmModalState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  onConfirm: () => void;
  isDangerous?: boolean;
}

export const AdminPanel: React.FC = () => {
  const { user, isAdmin, logout, loading: authLoading } = useAuth();
  const { t } = useTranslation();
  const [containers, setContainers] = useState<Container[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmModal, setConfirmModal] = useState<ConfirmModalState>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: t('common.confirm'),
    onConfirm: () => {},
    isDangerous: false
  });

  const loadContainers = useCallback(async () => {
    try {
      const response = await apiService.getAllContainers();
      if (response.success) {
        setContainers(response.containers);
        setError(null);
      } else {
        setError(response.error || t('admin.failedToLoadContainers'));
      }
    } catch (err: any) {
      setError(err.message || t('admin.failedToLoadContainers'));
    } finally {
      setLoading(false);
    }
  }, [t]);

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
    setConfirmModal({
      isOpen: true,
      title: t('admin.stopContainerTitle'),
      message: t('admin.stopContainerMessage', { containerName }),
      confirmText: t('common.stop'),
      isDangerous: true,
      onConfirm: () => stopContainer(containerId, containerName)
    });
  };

  const stopContainer = async (containerId: string, containerName: string) => {
    setConfirmModal({ ...confirmModal, isOpen: false });

    setActionLoading(true);
    try {
      const response = await apiService.stopAdminContainer(containerId);
      if (response.success) {
        setSuccessMessage(t('admin.containerStopped'));
        await loadContainers();
      } else {
        setError(response.error || t('admin.failedToStopContainer'));
      }
    } catch (err: any) {
      setError(err.message || t('admin.failedToStopContainer'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveContainer = async (containerId: string, containerName: string) => {
    setConfirmModal({
      isOpen: true,
      title: t('admin.removeContainerTitle'),
      message: t('admin.removeContainerMessage', { containerName }),
      confirmText: t('common.remove'),
      isDangerous: true,
      onConfirm: () => removeContainer(containerId, containerName)
    });
  };

  const removeContainer = async (containerId: string, containerName: string) => {
    setConfirmModal({ ...confirmModal, isOpen: false });

    setActionLoading(true);
    try {
      const response = await apiService.removeAdminContainer(containerId);
      if (response.success) {
        setSuccessMessage(t('admin.containerRemoved'));
        await loadContainers();
      } else {
        setError(response.error || t('admin.failedToRemoveContainer'));
      }
    } catch (err: any) {
      setError(err.message || t('admin.failedToRemoveContainer'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopAll = async () => {
    setConfirmModal({
      isOpen: true,
      title: t('admin.stopAllTitle'),
      message: t('admin.stopAllMessage'),
      confirmText: t('admin.stopAllConfirm'),
      isDangerous: true,
      onConfirm: () => stopAllContainers()
    });
  };

  const stopAllContainers = async () => {
    setConfirmModal({ ...confirmModal, isOpen: false });

    setActionLoading(true);
    try {
      const response = await apiService.stopAllContainers();
      if (response.success) {
        setSuccessMessage(t('admin.containersStopped', { count: response.stopped_count }));
        await loadContainers();
      } else {
        setError(response.error || t('admin.failedToStopAll'));
      }
    } catch (err: any) {
      setError(err.message || t('admin.failedToStopAll'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleCleanupStopped = async () => {
    setConfirmModal({
      isOpen: true,
      title: t('admin.removeStoppedTitle'),
      message: t('admin.removeStoppedMessage'),
      confirmText: t('admin.removeAllConfirm'),
      isDangerous: true,
      onConfirm: () => cleanupStoppedContainers()
    });
  };

  const cleanupStoppedContainers = async () => {
    setConfirmModal({ ...confirmModal, isOpen: false });

    setActionLoading(true);
    try {
      const response = await apiService.cleanupStoppedContainers();
      if (response.success) {
        setSuccessMessage(t('admin.containersRemoved', { count: response.removed_count }));
        await loadContainers();
      } else {
        setError(response.error || t('admin.failedToCleanup'));
      }
    } catch (err: any) {
      setError(err.message || t('admin.failedToCleanup'));
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return t('common.NA');
    return new Date(dateString).toLocaleString();
  };

  if (authLoading) {
    return (
      <div className="container">
        <Loading message={t('common.checkingSession')} />
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="container">
      <header className="header">
        <h1>⚙️ {t('admin.title')}</h1>
        <div className="user-info">
          <span className="username">{user?.username} ({t('admin.admin')})</span>
          <Link to="/admin/theme" className="btn btn-primary">
            {t('admin.themeSettings')}
          </Link>
          <Link to="/admin/desktop-types" className="btn btn-primary">
            {t('admin.desktopTypes')}
          </Link>
          <Link to="/" className="btn btn-secondary">
            {t('admin.backToDesktops')}
          </Link>
          <button className="btn btn-secondary" onClick={logout}>
            {t('common.logout')}
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
          <h2>{t('admin.containerManagement')}</h2>
          <div className="admin-actions">
            <button className="btn btn-primary" onClick={loadContainers} disabled={actionLoading}>
              🔄 {t('common.refresh')}
            </button>
            <button className="btn btn-danger" onClick={handleStopAll} disabled={actionLoading}>
              {t('admin.stopAll')}
            </button>
            <button className="btn btn-danger" onClick={handleCleanupStopped} disabled={actionLoading}>
              {t('admin.removeStopped')}
            </button>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">{t('admin.totalContainers')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.running}</div>
            <div className="stat-label">{t('admin.running')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.users}</div>
            <div className="stat-label">{t('admin.activeUsers')}</div>
          </div>
        </div>

        {loading ? (
          <Loading message={t('admin.loadingContainers')} />
        ) : containers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📦</div>
            <p>{t('admin.noContainers')}</p>
          </div>
        ) : (
          <table className="container-table">
            <thead>
              <tr>
                <th>{t('admin.tableUser')}</th>
                <th>{t('admin.tableContainerName')}</th>
                <th>{t('admin.tableStatus')}</th>
                <th>{t('admin.tablePort')}</th>
                <th>{t('admin.tableCreated')}</th>
                <th>{t('admin.tableLastAccessed')}</th>
                <th>{t('admin.tableActions')}</th>
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
                  <td>{container.host_port || t('common.NA')}</td>
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
                              {t('common.open')}
                            </button>
                          )}
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => handleStopContainer(container.id, container.container_name)}
                            disabled={actionLoading}
                          >
                            {t('common.stop')}
                          </button>
                        </>
                      )}
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleRemoveContainer(container.id, container.container_name)}
                        disabled={actionLoading}
                      >
                        {t('common.remove')}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Confirmation Modal */}
      {confirmModal.isOpen && (
        <div className="modal-overlay" onClick={() => setConfirmModal({ ...confirmModal, isOpen: false })}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{confirmModal.title}</h3>
              <button 
                className="modal-close" 
                onClick={() => setConfirmModal({ ...confirmModal, isOpen: false })}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>{confirmModal.message}</p>
            </div>
            <div className="modal-footer">
              <button 
                className="btn btn-secondary" 
                onClick={() => setConfirmModal({ ...confirmModal, isOpen: false })}
                disabled={actionLoading}
              >
                {t('common.cancel')}
              </button>
              <button 
                className={`btn ${confirmModal.isDangerous ? 'btn-danger' : 'btn-primary'}`}
                onClick={() => {
                  confirmModal.onConfirm();
                }}
                disabled={actionLoading}
              >
                {confirmModal.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}

      {actionLoading && (
        <div className="loading-overlay">
          <div className="loading-content">
            <Loading message={t('common.processing')} />
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
