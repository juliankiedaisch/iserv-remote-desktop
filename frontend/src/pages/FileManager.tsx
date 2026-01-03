import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
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
  is_shared?: boolean;
  assignment_info?: {
    id: number;
    folder_name: string;
    desktop_image_id: number;
  };
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
  const { t } = useTranslation();
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
        setError(response.data.error || t('fileManager.failedToLoadFiles'));
      }
    } catch (err: any) {
      setError(err.message || t('fileManager.failedToLoadFiles'));
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
      
      setSuccess(t('fileManager.uploadSuccess', { count: uploadedCount }));
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || t('fileManager.uploadFailed'));
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
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set dragOver to false if we're actually leaving the drop zone container
    // and not just entering a child element
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    
    if (x <= rect.left || x >= rect.right || y <= rect.top || y >= rect.bottom) {
      setDragOver(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
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
      setError(t('fileManager.downloadFailed'));
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
      setSuccess(t('fileManager.deleteSuccess'));
      setShowDeleteModal(false);
      setFileToDelete(null);
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || t('fileManager.deleteFailed'));
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
    // Only stop propagation if we're dragging an internal item
    // Allow external file drops to bubble up to the drop zone
    if (draggedItem) {
      e.stopPropagation();
      if (file.is_directory && draggedItem.path !== file.path) {
        e.dataTransfer.dropEffect = 'move';
        setDropTarget(file);
      }
    }
  };

  const handleFileDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    // Only stop propagation if we're dragging an internal item
    if (draggedItem) {
      e.stopPropagation();
    }
    setDropTarget(null);
  };

  const handleFileDrop = async (e: React.DragEvent, targetFolder: FileItem) => {
    e.preventDefault();
    setDropTarget(null);

    // Only handle internal item moves, let external drops bubble up
    if (!draggedItem) {
      return;
    }
    
    e.stopPropagation();

    if (!targetFolder.is_directory || draggedItem.path === targetFolder.path) {
      return;
    }

    try {
      const response = await apiService.post('/api/files/move', {
        space,
        source_path: draggedItem.path,
        destination_path: targetFolder.path,
      });
      
      let message = t('fileManager.moveSuccess', { source: draggedItem.name, target: targetFolder.name });
      
      // Check if assignments were updated
      if (response.data.updated_assignments && response.data.updated_assignments.length > 0) {
        const count = response.data.updated_assignments.length;
        message = t('fileManager.moveSuccessWithAssignments', { 
          source: draggedItem.name, 
          target: targetFolder.name,
          count 
        });
      }
      
      setSuccess(message);
      setDraggedItem(null);
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || t('fileManager.moveFailed'));
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
      setSuccess(t('fileManager.folderCreated'));
      setShowNewFolderModal(false);
      setNewFolderName('');
      loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.error || t('fileManager.folderCreateFailed'));
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
        <Loading message={t('common.checkingSession')} />
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
          <h2>📁 {t('fileManager.title')}</h2>
          <div className="space-tabs">
            <button
              className={`space-tab ${space === 'private' ? 'active' : ''}`}
              onClick={() => handleSpaceChange('private')}
            >
              🔒 {t('fileManager.private')}
            </button>
            <button
              className={`space-tab ${space === 'public' ? 'active' : ''}`}
              onClick={() => handleSpaceChange('public')}
            >
              🌐 {t('fileManager.public')}
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
              {space === 'private' ? `🏠 ${t('fileManager.home')}` : `🌐 ${t('fileManager.publicSpace')}`}
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
              📤 {t('fileManager.uploadFiles')}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setShowNewFolderModal(true)}
            >
              📁 {t('fileManager.newFolder')}
            </button>
            {currentPath && (
              <button className="btn btn-secondary" onClick={handleNavigateUp}>
                ⬆️ {t('fileManager.up')}
              </button>
            )}
            <button className="btn btn-secondary" onClick={loadFiles}>
              🔄 {t('common.refresh')}
            </button>
            <button 
              className="btn btn-secondary" 
              onClick={() => setShowHiddenFiles(!showHiddenFiles)}
            >
              {showHiddenFiles ? `👁️ ${t('fileManager.hideHiddenFiles')}` : `👁️‍🗨️ ${t('fileManager.showHiddenFiles')}`}
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
            <Loading message={t('fileManager.loadingFiles')} />
          ) : visibleFiles.length === 0 ? (
            <div className="empty-state">
              <p>{t('fileManager.noFiles')}</p>
              <p className="empty-hint">{t('fileManager.emptyHint')}</p>
            </div>
          ) : (
            <table className="file-table">
              <thead>
                <tr>
                  <th>{t('fileManager.fileName')}</th>
                  <th>{t('fileManager.fileSize')}</th>
                  <th>{t('fileManager.fileModified')}</th>
                  <th>{t('fileManager.actions')}</th>
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
                        {file.is_shared && (
                          <span 
                            className="shared-badge" 
                            title={t('fileManager.sharedBadge', { folderName: file.assignment_info?.folder_name || t('fileManager.sharedIndicator') })}
                          >
                            🔗
                          </span>
                        )}
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
                                <span>⬇️</span> {t('common.download')}
                              </button>
                            )}
                            <button
                              className="menu-item menu-item-danger"
                              onClick={() => handleMenuAction('delete', file)}
                            >
                              <span>🗑️</span> {t('common.delete')}
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
                <p>{t('fileManager.dropToUpload')}</p>
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
              <h2>{t('fileManager.createNewFolder')}</h2>
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
                placeholder={t('fileManager.folderName')}
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
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCreateFolder}
              >
                {t('common.create')}
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
              <h2>{t('fileManager.deleteConfirmTitle')}</h2>
              <button
                className="modal-close"
                onClick={() => setShowDeleteModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>{t('fileManager.deleteConfirmMessage')} <strong>"{fileToDelete.name}"</strong>?</p>
              {fileToDelete.is_directory && (
                <p className="warning-text">{t('fileManager.deleteWarning')}</p>
              )}
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowDeleteModal(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={confirmDelete}
              >
                {t('common.delete')}
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
                <h3>{t('fileManager.fileDetails')}</h3>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">{t('fileManager.fileName')}:</span>
                    <span className="info-value">{selectedFile.name}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t('fileManager.fileSize')}:</span>
                    <span className="info-value">{formatSize(selectedFile.size)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t('fileManager.fileModified')}:</span>
                    <span className="info-value">{formatDate(selectedFile.modified)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t('fileManager.fileType')}:</span>
                    <span className="info-value">
                      {getFileExtension(selectedFile.name).toUpperCase() || t('fileManager.unknown')}
                    </span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{t('fileManager.filePath')}:</span>
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
                {t('common.close')}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  handleDownload(selectedFile);
                  closeFileDetailsModal();
                }}
              >
                ⬇️ {t('common.download')}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => {
                  closeFileDetailsModal();
                  handleDelete(selectedFile);
                }}
              >
                🗑️ {t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileManager;
