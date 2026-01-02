import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Header, Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import { apiService } from '../services/api';
import './FileManager.css';

interface FileItem {
  name: string;
  path: string;
  is_directory: boolean;
  size: number | null;
  modified: string;
}

interface FileListResponse {
  success: boolean;
  items: FileItem[];
  current_path: string;
  error?: string;
}

export const FileManager: React.FC = () => {
  const { user, isAdmin, isTeacher, logout, loading: authLoading } = useAuth();
  const { themeData } = useTheme();
  const [space, setSpace] = useState<'private' | 'public'>('private');
  const [currentPath, setCurrentPath] = useState<string>('');
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showNewFolderModal, setShowNewFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiService.get<FileListResponse>(
        `/api/files/list?space=${space}&path=${encodeURIComponent(currentPath)}`
      );
      if (response.data.success) {
        setFiles(response.data.items);
      } else {
        setError(response.data.error || 'Failed to load files');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load files');
    } finally {
      setLoading(false);
    }
  }, [space, currentPath]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleSpaceChange = (newSpace: 'private' | 'public') => {
    setSpace(newSpace);
    setCurrentPath('');
  };

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
  };

  const handleNavigateUp = () => {
    if (currentPath) {
      const parts = currentPath.split('/').filter(p => p);
      parts.pop();
      setCurrentPath(parts.join('/'));
    }
  };

  const handleFileUpload = async (files: FileList) => {
    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('space', space);
        formData.append('path', currentPath);

        await apiService.post('/api/files/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
      }
      setSuccess(`${files.length} file(s) uploaded successfully`);
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to upload files');
    } finally {
      setUploading(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const handleDownload = async (file: FileItem) => {
    try {
      const response = await apiService.get(
        `/api/files/download?space=${space}&path=${encodeURIComponent(file.path)}`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', file.name);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError('Failed to download file');
    }
  };

  const handleDelete = async (file: FileItem) => {
    if (!window.confirm(`Are you sure you want to delete "${file.name}"?`)) {
      return;
    }

    try {
      await apiService.delete(`/api/files/delete?space=${space}&path=${encodeURIComponent(file.path)}`);
      setSuccess('Deleted successfully');
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete');
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      return;
    }

    try {
      await apiService.post('/api/files/create-folder', {
        space,
        path: currentPath,
        folder_name: newFolderName,
      });
      setSuccess('Folder created successfully');
      setShowNewFolderModal(false);
      setNewFolderName('');
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to create folder');
    }
  };

  const formatSize = (bytes: number | null): string => {
    if (bytes === null) return '-';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  if (authLoading) {
    return (
      <div className="container">
        <Loading message="Checking session..." />
      </div>
    );
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

      <div className="file-manager">
        <div className="file-manager-header">
          <h2>📁 File Manager</h2>
          <div className="space-tabs">
            <button
              className={`space-tab ${space === 'private' ? 'active' : ''}`}
              onClick={() => handleSpaceChange('private')}
            >
              🔒 Private Files
            </button>
            <button
              className={`space-tab ${space === 'public' ? 'active' : ''}`}
              onClick={() => handleSpaceChange('public')}
            >
              🌐 Public Files
            </button>
          </div>
        </div>

        {error && (
          <Alert type="error" message={error} onDismiss={() => setError(null)} />
        )}

        {success && (
          <Alert type="success" message={success} onDismiss={() => setSuccess(null)} />
        )}

        <div className="file-manager-toolbar">
          <div className="breadcrumb">
            <button onClick={() => setCurrentPath('')} className="breadcrumb-item">
              {space === 'private' ? '🏠 Home' : '🌐 Public'}
            </button>
            {currentPath.split('/').filter(p => p).map((part, index, arr) => {
              const path = arr.slice(0, index + 1).join('/');
              return (
                <React.Fragment key={path}>
                  <span className="breadcrumb-separator">/</span>
                  <button onClick={() => handleNavigate(path)} className="breadcrumb-item">
                    {part}
                  </button>
                </React.Fragment>
              );
            })}
          </div>

          <div className="toolbar-actions">
            <button
              className="btn btn-primary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              📤 Upload Files
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setShowNewFolderModal(true)}
            >
              📁 New Folder
            </button>
            {currentPath && (
              <button className="btn btn-secondary" onClick={handleNavigateUp}>
                ⬆️ Up
              </button>
            )}
            <button className="btn btn-secondary" onClick={loadFiles}>
              🔄 Refresh
            </button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileInputChange}
          />
        </div>

        <div
          className={`file-drop-zone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {loading ? (
            <Loading message="Loading files..." />
          ) : files.length === 0 ? (
            <div className="empty-state">
              <p>No files here yet</p>
              <p className="empty-hint">Drag and drop files here or click "Upload Files"</p>
            </div>
          ) : (
            <table className="file-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Size</th>
                  <th>Modified</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <tr key={file.path}>
                    <td>
                      {file.is_directory ? (
                        <button
                          className="file-name-button"
                          onClick={() => handleNavigate(file.path)}
                        >
                          📁 {file.name}
                        </button>
                      ) : (
                        <span>📄 {file.name}</span>
                      )}
                    </td>
                    <td>{formatSize(file.size)}</td>
                    <td>{formatDate(file.modified)}</td>
                    <td className="file-actions">
                      {!file.is_directory && (
                        <button
                          className="btn-icon"
                          onClick={() => handleDownload(file)}
                          title="Download"
                        >
                          ⬇️
                        </button>
                      )}
                      <button
                        className="btn-icon btn-danger"
                        onClick={() => handleDelete(file)}
                        title="Delete"
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {dragOver && (
            <div className="drag-overlay">
              <div className="drag-message">
                <p>📤</p>
                <p>Drop files here to upload</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Folder Modal */}
      {showNewFolderModal && (
        <div className="modal-overlay" onClick={() => setShowNewFolderModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Folder</h2>
              <button
                className="modal-close"
                onClick={() => setShowNewFolderModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <input
                type="text"
                className="form-control"
                placeholder="Folder name"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateFolder();
                  }
                }}
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowNewFolderModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCreateFolder}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileManager;
