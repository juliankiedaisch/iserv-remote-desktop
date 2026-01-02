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
  const [showHiddenFiles, setShowHiddenFiles] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<FileItem | null>(null);
  const [draggedItem, setDraggedItem] = useState<FileItem | null>(null);
  const [dropTarget, setDropTarget] = useState<FileItem | null>(null);
  const [openMenuPath, setOpenMenuPath] = useState<string | null>(null);
  const [showFileDetailsModal, setShowFileDetailsModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
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
      // Upload files in batches to balance performance and server load
      // Batch size of 3 allows parallel uploads while preventing server overload
      // and maintaining reasonable memory usage for large file sets
      const fileArray = Array.from(files);
      const batchSize = 3;
      let uploadedCount = 0;
      
      for (let i = 0; i < fileArray.length; i += batchSize) {
        const batch = fileArray.slice(i, i + batchSize);
        const uploadPromises = batch.map(file => {
          const formData = new FormData();
          formData.append('file', file);
          formData.append('space', space);
          formData.append('path', currentPath);

          return apiService.post('/api/files/upload', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });
        });

        await Promise.all(uploadPromises);
        uploadedCount += batch.length;
      }
      
      setSuccess(`${uploadedCount} file(s) uploaded successfully`);
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
      
      const url = window.URL.createObjectURL(response.data);
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

  const handleDelete = (file: FileItem) => {
    setFileToDelete(file);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    if (!fileToDelete) return;

    try {
      await apiService.delete(`/api/files/delete?space=${space}&path=${encodeURIComponent(fileToDelete.path)}`);
      setSuccess('Deleted successfully');
      setShowDeleteModal(false);
      setFileToDelete(null);
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete');
      setShowDeleteModal(false);
      setFileToDelete(null);
    }
  };

  const handleDragStart = (e: React.DragEvent, file: FileItem) => {
    setDraggedItem(file);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
    setDropTarget(null);
  };

  const handleFileDragOver = (e: React.DragEvent, file: FileItem) => {
    e.preventDefault();
    e.stopPropagation();
    if (draggedItem && file.is_directory && draggedItem.path !== file.path) {
      e.dataTransfer.dropEffect = 'move';
      setDropTarget(file);
    }
  };

  const handleFileDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDropTarget(null);
  };

  const handleFileDrop = async (e: React.DragEvent, targetFolder: FileItem) => {
    e.preventDefault();
    e.stopPropagation();
    setDropTarget(null);

    if (!draggedItem || !targetFolder.is_directory || draggedItem.path === targetFolder.path) {
      return;
    }

    try {
      await apiService.post('/api/files/move', {
        space,
        source_path: draggedItem.path,
        destination_path: targetFolder.path,
      });
      setSuccess(`Moved "${draggedItem.name}" to "${targetFolder.name}"`);
      setDraggedItem(null);
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to move file');
      setDraggedItem(null);
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

  const visibleFiles = showHiddenFiles 
    ? files 
    : files.filter(file => !file.name.startsWith('.'));

  const toggleMenu = (path: string) => {
    setOpenMenuPath(openMenuPath === path ? null : path);
  };

  const handleMenuAction = (action: 'download' | 'delete', file: FileItem) => {
    setOpenMenuPath(null);
    if (action === 'download') {
      handleDownload(file);
    } else if (action === 'delete') {
      handleDelete(file);
    }
  };

  const getFileExtension = (filename: string): string => {
    const parts = filename.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
  };

  const isPreviewable = (file: FileItem): boolean => {
    if (file.is_directory) return false;
    const ext = getFileExtension(file.name);
    const previewableExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'txt', 'md', 'json', 'xml', 'csv', 'log', 'pdf'];
    return previewableExtensions.includes(ext);
  };

  const handleFileClick = async (file: FileItem) => {
    if (file.is_directory) {
      handleNavigate(file.path);
      return;
    }
    
    setSelectedFile(file);
    setShowFileDetailsModal(true);
    
    // Generate preview if possible
    if (isPreviewable(file)) {
      try {
        const ext = getFileExtension(file.name);
        const response = await apiService.get(
          `/api/files/download?space=${space}&path=${encodeURIComponent(file.path)}`,
          { responseType: ext === 'pdf' || ext.match(/jpg|jpeg|png|gif|bmp|webp|svg/) ? 'blob' : 'text' }
        );
        
        if (ext === 'pdf' || ext.match(/jpg|jpeg|png|gif|bmp|webp|svg/)) {
          const url = window.URL.createObjectURL(response.data);
          setPreviewUrl(url);
        } else {
          // For text files, we'll store as text
          setPreviewUrl(response.data);
        }
      } catch (err) {
        console.error('Failed to load preview:', err);
      }
    }
  };

  const closeFileDetailsModal = () => {
    setShowFileDetailsModal(false);
    setSelectedFile(null);
    if (previewUrl && typeof previewUrl === 'string' && previewUrl.startsWith('blob:')) {
      window.URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
  };

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (openMenuPath) {
        setOpenMenuPath(null);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [openMenuPath]);

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
            <button 
              className="btn btn-secondary" 
              onClick={() => setShowHiddenFiles(!showHiddenFiles)}
            >
              {showHiddenFiles ? '👁️ Hide Hidden' : '👁️‍🗨️ Show Hidden'}
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
          ) : visibleFiles.length === 0 ? (
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
                {visibleFiles.map((file) => (
                  <tr 
                    key={file.path}
                    draggable
                    onDragStart={(e) => handleDragStart(e, file)}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleFileDragOver(e, file)}
                    onDragLeave={handleFileDragLeave}
                    onDrop={(e) => handleFileDrop(e, file)}
                    className={`${
                      draggedItem?.path === file.path ? 'dragging' : ''
                    } ${
                      dropTarget?.path === file.path ? 'drop-target' : ''
                    }`}
                  >
                    <td>
                      <button
                        className="file-name-button"
                        onClick={() => handleFileClick(file)}
                      >
                        {file.is_directory ? '📁' : '📄'} {file.name}
                      </button>
                    </td>
                    <td>{formatSize(file.size)}</td>
                    <td>{formatDate(file.modified)}</td>
                    <td className="file-actions">
                      <div className="action-menu-container">
                        <button
                          className="btn-menu"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleMenu(file.path);
                          }}
                          title="Actions"
                        >
                          ⋮
                        </button>
                        {openMenuPath === file.path && (
                          <div className="action-menu-dropdown">
                            {!file.is_directory && (
                              <button
                                className="menu-item"
                                onClick={() => handleMenuAction('download', file)}
                              >
                                <span>⬇️</span> Download
                              </button>
                            )}
                            <button
                              className="menu-item menu-item-danger"
                              onClick={() => handleMenuAction('delete', file)}
                            >
                              <span>🗑️</span> Delete
                            </button>
                          </div>
                        )}
                      </div>
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

      {/* Delete Confirmation Modal */}
      {showDeleteModal && fileToDelete && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Confirm Delete</h2>
              <button
                className="modal-close"
                onClick={() => setShowDeleteModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete <strong>"{fileToDelete.name}"</strong>?</p>
              {fileToDelete.is_directory && (
                <p className="warning-text">This will delete the folder and all its contents.</p>
              )}
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowDeleteModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={confirmDelete}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* File Details Modal */}
      {showFileDetailsModal && selectedFile && (
        <div className="modal-overlay" onClick={closeFileDetailsModal}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📄 {selectedFile.name}</h2>
              <button
                className="modal-close"
                onClick={closeFileDetailsModal}
              >
                ✕
              </button>
            </div>
            <div className="modal-body file-details-body">
              {/* Preview Section */}
              {isPreviewable(selectedFile) && previewUrl && (
                <div className="file-preview">
                  {getFileExtension(selectedFile.name).match(/jpg|jpeg|png|gif|bmp|webp|svg/) && (
                    <img src={previewUrl} alt={selectedFile.name} className="preview-image" />
                  )}
                  {getFileExtension(selectedFile.name) === 'pdf' && (
                    <iframe src={previewUrl} className="preview-pdf" title={selectedFile.name} />
                  )}
                  {getFileExtension(selectedFile.name).match(/txt|md|json|xml|csv|log/) && (
                    <pre className="preview-text">{previewUrl}</pre>
                  )}
                </div>
              )}
              
              {/* File Information */}
              <div className="file-info">
                <h3>File Information</h3>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">Name:</span>
                    <span className="info-value">{selectedFile.name}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Size:</span>
                    <span className="info-value">{formatSize(selectedFile.size)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Modified:</span>
                    <span className="info-value">{formatDate(selectedFile.modified)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Type:</span>
                    <span className="info-value">
                      {getFileExtension(selectedFile.name).toUpperCase() || 'Unknown'}
                    </span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Path:</span>
                    <span className="info-value path-value">{selectedFile.path}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={closeFileDetailsModal}
              >
                Close
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  handleDownload(selectedFile);
                  closeFileDetailsModal();
                }}
              >
                ⬇️ Download
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => {
                  closeFileDetailsModal();
                  handleDelete(selectedFile);
                }}
              >
                🗑️ Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileManager;
