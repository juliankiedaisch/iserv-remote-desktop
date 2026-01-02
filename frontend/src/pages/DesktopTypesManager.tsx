import React, { useState, useEffect } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { wsService } from '../services/websocket';
import './DesktopTypesManager.css';

interface DesktopType {
  id: number;
  name: string;
  docker_image: string;
  description: string | null;
  icon: string;
  enabled: boolean;
  assignment_count: number;
}

export const DesktopTypesManager: React.FC = () => {
  const { user, isAdmin, loading: authLoading } = useAuth();
  const [desktopTypes, setDesktopTypes] = useState<DesktopType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedType, setSelectedType] = useState<DesktopType | null>(null);
  const [pullingImages, setPullingImages] = useState<Set<number>>(new Set());
  const [pullProgress, setPullProgress] = useState<Record<number, string>>({});
  const [selectedTypes, setSelectedTypes] = useState<Set<number>>(new Set());
  const [showPullModal, setShowPullModal] = useState(false);
  const [pullLogs, setPullLogs] = useState<Array<{image: string, message: string, timestamp: number}>>([]);
  const [iconFile, setIconFile] = useState<File | null>(null);
  const [iconPreview, setIconPreview] = useState<string | null>(null);
  const [uploadingIcon, setUploadingIcon] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    docker_image: '',
    description: '',
    icon: '🖥️',
    enabled: true
  });

  useEffect(() => {
    if (isAdmin) {
      loadDesktopTypes();
    }
  }, [isAdmin]);

  useEffect(() => {
    // Connect to WebSocket
    wsService.connect();

    // Listen for image pull events
    const unsubscribe = wsService.onImagePull((event, data) => {
      const typeId = desktopTypes.find(dt => dt.docker_image === data.image)?.id;
      
      if (event === 'started') {
        if (typeId) {
          setPullingImages(prev => new Set(prev).add(typeId));
          setPullProgress(prev => ({ ...prev, [typeId]: 'Starting...' }));
        }
        setPullLogs(prev => [...prev, { 
          image: data.image, 
          message: data.message || 'Starting pull...', 
          timestamp: Date.now() 
        }]);
      } else if (event === 'progress') {
        if (typeId && data.progress) {
          setPullProgress(prev => ({ ...prev, [typeId]: data.progress }));
        }
        // Only log significant progress updates to avoid spam
        if (data.status === 'Downloading' || data.status === 'Extracting' || data.status === 'Pull complete') {
          setPullLogs(prev => {
            const recent = prev.slice(-100); // Keep last 100 logs
            return [...recent, { 
              image: data.image, 
              message: data.message || data.status, 
              timestamp: Date.now() 
            }];
          });
        }
      } else if (event === 'completed') {
        if (typeId) {
          setPullingImages(prev => {
            const next = new Set(prev);
            next.delete(typeId);
            return next;
          });
          setPullProgress(prev => {
            const next = { ...prev };
            delete next[typeId];
            return next;
          });
        }
        setPullLogs(prev => [...prev, { 
          image: data.image, 
          message: '✅ ' + (data.message || 'Pull completed'), 
          timestamp: Date.now() 
        }]);
        setSuccessMessage(`Successfully pulled ${data.image}`);
      } else if (event === 'error') {
        if (typeId) {
          setPullingImages(prev => {
            const next = new Set(prev);
            next.delete(typeId);
            return next;
          });
          setPullProgress(prev => {
            const next = { ...prev };
            delete next[typeId];
            return next;
          });
        }
        setPullLogs(prev => [...prev, { 
          image: data.image, 
          message: '❌ ' + (data.error || 'Pull failed'), 
          timestamp: Date.now() 
        }]);
        setError(`Failed to pull ${data.image}: ${data.error}`);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [desktopTypes]);

  const loadDesktopTypes = async () => {
    try {
      const response = await fetch('/api/admin/desktops/types', {
        headers: {
          'X-Session-ID': localStorage.getItem('session_id') || '',
        }
      });
      const data = await response.json();
      
      if (data.success) {
        setDesktopTypes(data.desktop_types);
        setError(null);
      } else {
        setError(data.error || 'Failed to load desktop types');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load desktop types');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Upload icon if file is selected
      let iconUrl = formData.icon;
      if (iconFile) {
        const uploadedUrl = await uploadIconImage();
        if (uploadedUrl) {
          iconUrl = uploadedUrl;
        }
      }

      const response = await fetch('/api/admin/desktops/types', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': localStorage.getItem('session_id') || '',
        },
        body: JSON.stringify({ ...formData, icon: iconUrl })
      });
      const data = await response.json();

      if (data.success) {
        setSuccessMessage('Desktop type created successfully');
        setShowCreateModal(false);
        resetForm();
        await loadDesktopTypes();
      } else {
        setError(data.error || 'Failed to create desktop type');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create desktop type');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedType) return;

    setLoading(true);

    try {
      // Upload icon if new file is selected
      let iconUrl = formData.icon;
      if (iconFile) {
        const uploadedUrl = await uploadIconImage();
        if (uploadedUrl) {
          iconUrl = uploadedUrl;
        }
      }

      const response = await fetch(`/api/admin/desktops/types/${selectedType.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': localStorage.getItem('session_id') || '',
        },
        body: JSON.stringify({ ...formData, icon: iconUrl })
      });
      const data = await response.json();

      if (data.success) {
        setSuccessMessage('Desktop type updated successfully');
        setShowEditModal(false);
        setSelectedType(null);
        resetForm();
        await loadDesktopTypes();
      } else {
        setError(data.error || 'Failed to update desktop type');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to update desktop type');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (typeId: number, typeName: string) => {
    if (!window.confirm(`Delete desktop type "${typeName}"? This will remove all assignments.`)) {
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`/api/admin/desktops/types/${typeId}`, {
        method: 'DELETE',
        headers: {
          'X-Session-ID': localStorage.getItem('session_id') || '',
        }
      });
      const data = await response.json();

      if (data.success) {
        setSuccessMessage('Desktop type deleted successfully');
        await loadDesktopTypes();
      } else {
        setError(data.error || 'Failed to delete desktop type');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete desktop type');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      docker_image: '',
      description: '',
      icon: '🖥️',
      enabled: true
    });
    setIconFile(null);
    setIconPreview(null);
  };

  const openEditModal = (type: DesktopType) => {
    setSelectedType(type);
    setFormData({
      name: type.name,
      docker_image: type.docker_image,
      description: type.description || '',
      icon: type.icon,
      enabled: type.enabled
    });
    setIconFile(null);
    // If icon is a URL path, set it as preview
    if (type.icon.startsWith('/api/')) {
      setIconPreview(type.icon);
    } else {
      setIconPreview(null);
    }
    setShowEditModal(true);
  };

  const handleIconFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/svg+xml', 'image/webp'];
      if (!allowedTypes.includes(file.type)) {
        setError('Invalid file type. Please upload PNG, JPG, GIF, SVG, or WebP.');
        return;
      }
      
      // Validate file size (2MB max)
      if (file.size > 2 * 1024 * 1024) {
        setError('File too large. Maximum size is 2MB.');
        return;
      }
      
      setIconFile(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setIconPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const uploadIconImage = async (): Promise<string | null> => {
    if (!iconFile) return null;
    
    setUploadingIcon(true);
    try {
      const formData = new FormData();
      formData.append('icon', iconFile);
      
      const response = await fetch('/api/admin/desktops/icons/upload', {
        method: 'POST',
        headers: {
          'X-Session-ID': localStorage.getItem('session_id') || '',
        },
        body: formData
      });
      
      const data = await response.json();
      
      if (data.success) {
        return data.icon_url;
      } else {
        setError(data.error || 'Failed to upload icon');
        return null;
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload icon');
      return null;
    } finally {
      setUploadingIcon(false);
    }
  };

  const handlePullImage = async (typeId: number) => {
    setPullingImages(prev => new Set(prev).add(typeId));
    setPullProgress(prev => ({ ...prev, [typeId]: 'Initializing...' }));
    setPullLogs([]);
    setShowPullModal(true);

    try {
      const response = await fetch(`/api/admin/desktops/types/${typeId}/pull-image`, {
        method: 'POST',
        headers: {
          'X-Session-ID': localStorage.getItem('session_id') || '',
        }
      });
      const data = await response.json();

      if (!data.success) {
        setError(data.error || 'Failed to pull image');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to pull image');
      setPullingImages(prev => {
        const next = new Set(prev);
        next.delete(typeId);
        return next;
      });
    }
  };

  const handlePullMultipleImages = async () => {
    if (selectedTypes.size === 0) {
      setError('Please select at least one desktop type');
      return;
    }

    setPullLogs([]);
    setShowPullModal(true);
    selectedTypes.forEach(id => {
      setPullingImages(prev => new Set(prev).add(id));
      setPullProgress(prev => ({ ...prev, [id]: 'Queued...' }));
    });

    try {
      const response = await fetch('/api/admin/desktops/pull-images', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': localStorage.getItem('session_id') || '',
        },
        body: JSON.stringify({ type_ids: Array.from(selectedTypes) })
      });
      const data = await response.json();

      if (!data.success) {
        setError('Some images failed to pull. Check the logs for details.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to pull images');
    } finally {
      setSelectedTypes(new Set());
    }
  };

  const toggleSelection = (typeId: number) => {
    setSelectedTypes(prev => {
      const next = new Set(prev);
      if (next.has(typeId)) {
        next.delete(typeId);
      } else {
        next.add(typeId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedTypes.size === desktopTypes.length) {
      setSelectedTypes(new Set());
    } else {
      setSelectedTypes(new Set(desktopTypes.map(dt => dt.id)));
    }
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
        <h1>🖥️ Desktop Types Manager</h1>
        <div className="user-info">
          <span className="username">{user?.username} (Admin)</span>
          <Link to="/admin" className="btn btn-secondary">
            ← Back to Admin
          </Link>
        </div>
      </header>

      {error && (
        <Alert type="error" message={error} onDismiss={() => setError(null)} />
      )}
      {successMessage && (
        <Alert type="success" message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <div className="desktop-types-container">
        <div className="desktop-types-header">
          <h2>Available Desktop Types</h2>
          <div className="header-actions">
            {selectedTypes.size > 0 && (
              <>
                <span className="selection-count">{selectedTypes.size} selected</span>
                <button 
                  className="btn btn-secondary" 
                  onClick={handlePullMultipleImages}
                  disabled={pullingImages.size > 0}
                >
                  🔄 Pull Selected ({selectedTypes.size})
                </button>
              </>
            )}
            <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
              ➕ Create New Type
            </button>
          </div>
        </div>

        {loading ? (
          <Loading message="Loading desktop types..." />
        ) : desktopTypes.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📦</div>
            <p>No desktop types configured</p>
            <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
              Create First Desktop Type
            </button>
          </div>
        ) : (
          <>
            {desktopTypes.length > 0 && (
              <div className="bulk-actions">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectedTypes.size === desktopTypes.length && desktopTypes.length > 0}
                    onChange={toggleSelectAll}
                  />
                  Select All
                </label>
              </div>
            )}
            <div className="desktop-types-grid">
              {desktopTypes.map((type) => (
              <div key={type.id} className={`desktop-type-card ${!type.enabled ? 'disabled' : ''} ${selectedTypes.has(type.id) ? 'selected' : ''}`}>
                <div className="card-header-select">
                  <input
                    type="checkbox"
                    checked={selectedTypes.has(type.id)}
                    onChange={() => toggleSelection(type.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>
                <div className="desktop-type-icon">
                  {type.icon.startsWith('/api/') ? (
                    <img src={type.icon} alt={type.name} className="icon-image" />
                  ) : (
                    <span>{type.icon}</span>
                  )}
                </div>
                <h3>{type.name}</h3>
                <p className="desktop-type-description">{type.description || 'No description'}</p>
                <div className="desktop-type-meta">
                  <span className="desktop-type-image">{type.docker_image}</span>
                  <span className={`status-badge ${type.enabled ? 'enabled' : 'disabled'}`}>
                    {type.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <span className="assignment-count">
                    {type.assignment_count} assignment{type.assignment_count !== 1 ? 's' : ''}
                  </span>
                </div>
                {pullingImages.has(type.id) && (
                  <div className="pull-progress">
                    <div className="progress-spinner">⏳</div>
                    <span className="progress-text">{pullProgress[type.id] || 'Pulling...'}</span>
                  </div>
                )}
                <div className="desktop-type-actions">
                  <button 
                    className="btn btn-sm btn-secondary" 
                    onClick={() => handlePullImage(type.id)}
                    disabled={pullingImages.has(type.id)}
                  >
                    {pullingImages.has(type.id) ? '⏳ Pulling...' : '🔄 Pull Image'}
                  </button>
                  <button className="btn btn-sm btn-primary" onClick={() => openEditModal(type)}>
                    Edit
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(type.id, type.name)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
            </div>
          </>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create Desktop Type</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Docker Image *</label>
                <input
                  type="text"
                  value={formData.docker_image}
                  onChange={(e) => setFormData({ ...formData, docker_image: e.target.value })}
                  placeholder="e.g., kasmweb/ubuntu-jammy-desktop:1.15.0"
                  required
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label>Icon</label>
                <div className="icon-upload-container">
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/gif,image/svg+xml,image/webp"
                    onChange={handleIconFileChange}
                    className="file-input"
                  />
                  {iconPreview && (
                    <div className="icon-preview">
                      <img src={iconPreview} alt="Icon preview" />
                    </div>
                  )}
                  <small className="form-hint">Upload PNG, JPG, GIF, SVG, or WebP (max 2MB)</small>
                </div>
              </div>
              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  />
                  Enabled
                </label>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading || uploadingIcon}>
                  {uploadingIcon ? 'Uploading...' : loading ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && selectedType && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Edit Desktop Type</h2>
              <button className="modal-close" onClick={() => setShowEditModal(false)}>✕</button>
            </div>
            <form onSubmit={handleUpdate}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Docker Image *</label>
                <input
                  type="text"
                  value={formData.docker_image}
                  onChange={(e) => setFormData({ ...formData, docker_image: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label>Icon</label>
                <div className="icon-upload-container">
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/gif,image/svg+xml,image/webp"
                    onChange={handleIconFileChange}
                    className="file-input"
                  />
                  {iconPreview && (
                    <div className="icon-preview">
                      <img src={iconPreview} alt="Icon preview" />
                    </div>
                  )}
                  <small className="form-hint">
                    {iconFile ? 'New icon selected' : 'Upload new icon or keep existing'} (PNG, JPG, GIF, SVG, or WebP, max 2MB)
                  </small>
                </div>
              </div>
              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  />
                  Enabled
                </label>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading || uploadingIcon}>
                  {uploadingIcon ? 'Uploading...' : loading ? 'Updating...' : 'Update'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Pull Progress Modal */}
      {showPullModal && (
        <div className="modal-overlay" onClick={() => setShowPullModal(false)}>
          <div className="modal-content pull-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🔄 Pulling Docker Images</h2>
              <button className="modal-close" onClick={() => setShowPullModal(false)}>✕</button>
            </div>
            <div className="pull-logs-container">
              {pullLogs.length === 0 ? (
                <div className="pull-log-entry">
                  <span className="log-message">Initializing pull operation...</span>
                </div>
              ) : (
                pullLogs.map((log, index) => (
                  <div key={index} className="pull-log-entry">
                    <span className="log-image">{log.image.split('/').pop()}</span>
                    <span className="log-message">{log.message}</span>
                  </div>
                ))
              )}
            </div>
            <div className="modal-actions">
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={() => setShowPullModal(false)}
                disabled={pullingImages.size > 0}
              >
                {pullingImages.size > 0 ? 'Pulling in progress...' : 'Close'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DesktopTypesManager;
