import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiService } from '../services/api';
import './AssignmentManager.css';

interface DesktopImage {
  id: number;
  name: string;
  docker_image: string;
  description: string;
  icon: string;
}

interface Group {
  id: number;
  name: string;
  external_id: string;
}

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
}

interface Assignment {
  id: number;
  desktop_image_id: number;
  group_id: number | null;
  user_id: string | null;
  assignment_folder_path: string | null;
  assignment_folder_name: string | null;
  created_by: string;
  created_at: string;
  desktop_image?: DesktopImage;
  group?: { id: number; name: string };
  assigned_user?: { id: string; username: string };
  teacher?: { id: string; username: string };
  groups?: { id: number; name: string }[];
  assigned_users?: { id: string; username: string }[];
}

interface FileItem {
  name: string;
  path: string;
  is_directory: boolean;
  size: number | null;
  modified: string;
}

export const AssignmentManager: React.FC = () => {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [desktopImages, setDesktopImages] = useState<DesktopImage[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState<Assignment | null>(null);
  const [assignmentToDelete, setAssignmentToDelete] = useState<Assignment | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    desktop_image_id: '',
    group_ids: [] as number[],
    user_ids: [] as string[],
    assignment_folder_path: '',
    assignment_folder_name: '',
  });

  // Folder browser state
  const [showFolderBrowser, setShowFolderBrowser] = useState(false);
  const [currentBrowserPath, setCurrentBrowserPath] = useState<string>('');
  const [browserFiles, setBrowserFiles] = useState<FileItem[]>([]);
  const [loadingBrowser, setLoadingBrowser] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [assignmentsRes, imagesRes, groupsRes] = await Promise.all([
        apiService.get('/api/teacher/assignments'),
        apiService.get('/api/teacher/desktop-images'),
        apiService.get('/api/teacher/groups'),
      ]);

      setAssignments(assignmentsRes.data.assignments || []);
      setDesktopImages(imagesRes.data.images || []);
      setGroups(groupsRes.data.groups || []);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load data');
      console.error('Error loading data:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async (groupId?: number) => {
    try {
      const url = groupId
        ? `/api/teacher/users?group_id=${groupId}`
        : '/api/teacher/users';
      const res = await apiService.get(url);
      setUsers(res.data.users || []);
    } catch (err: any) {
      console.error('Error loading users:', err);
    }
  };

  const loadBrowserFiles = async (path: string = '') => {
    setLoadingBrowser(true);
    try {
      const response = await apiService.get(
        `/api/files/list?space=private&path=${encodeURIComponent(path)}`
      );
      if (response.data.success) {
        // Only show directories
        const directories = response.data.items.filter((item: FileItem) => item.is_directory);
        setBrowserFiles(directories);
      }
    } catch (err: any) {
      console.error('Error loading folders:', err);
    } finally {
      setLoadingBrowser(false);
    }
  };

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = {
        desktop_image_id: parseInt(formData.desktop_image_id),
        group_ids: formData.group_ids,
        user_ids: formData.user_ids,
        assignment_folder_path: selectedFolder,
        assignment_folder_name: selectedFolder ? selectedFolder.split('/').pop() : null,
      };

      await apiService.post('/api/teacher/assignments', payload);
      setShowCreateModal(false);
      resetForm();
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to create assignment');
    }
  };

  const handleUpdateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAssignment) return;

    try {
      await apiService.put(`/api/teacher/assignments/${selectedAssignment.id}`, {
        assignment_folder_path: selectedFolder,
        assignment_folder_name: selectedFolder ? selectedFolder.split('/').pop() : null,
      });
      setShowEditModal(false);
      setSelectedAssignment(null);
      resetForm();
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to update assignment');
    }
  };

  const handleDeleteAssignment = (assignment: Assignment) => {
    setAssignmentToDelete(assignment);
    setShowDeleteModal(true);
  };

  const confirmDeleteAssignment = async () => {
    if (!assignmentToDelete) return;

    try {
      await apiService.delete(`/api/teacher/assignments/${assignmentToDelete.id}`);
      setShowDeleteModal(false);
      setAssignmentToDelete(null);
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete assignment');
    }
  };

  const openCreateModal = () => {
    resetForm();
    loadUsers();
    setShowCreateModal(true);
  };

  const openEditModal = (assignment: Assignment) => {
    setSelectedAssignment(assignment);
    setFormData({
      desktop_image_id: assignment.desktop_image_id.toString(),
      group_ids: assignment.group_id ? [assignment.group_id] : [],
      user_ids: assignment.user_id ? [assignment.user_id] : [],
      assignment_folder_path: assignment.assignment_folder_path || '',
      assignment_folder_name: assignment.assignment_folder_name || '',
    });
    if (assignment.assignment_folder_path) {
      setSelectedFolder(assignment.assignment_folder_path);
    }
    setShowEditModal(true);
  };

  const resetForm = () => {
    setFormData({
      desktop_image_id: '',
      group_ids: [],
      user_ids: [],
      assignment_folder_path: '',
      assignment_folder_name: '',
    });
    setSelectedFolder(null);
    setCurrentBrowserPath('');
    setBrowserFiles([]);
  };



  if (loading) {
    return <div className="assignment-manager"><div className="loading">Loading...</div></div>;
  }

  return (
    <div className="assignment-manager">
      <div className="header">
        <h1>📚 Assignment Manager</h1>
        <div className="header-actions">
          <button className="btn btn-primary" onClick={openCreateModal}>
            + Create Assignment
          </button>
          <Link to="/" className="btn btn-secondary">
            ← Back to Desktops
          </Link>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="assignments-list">
        {assignments.length === 0 ? (
          <div className="empty-state">
            <p>No assignments yet. Create one to get started!</p>
          </div>
        ) : (
          <table className="assignments-table">
            <thead>
              <tr>
                <th>Desktop Image</th>
                <th>Assigned To</th>
                <th>Folder</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment) => (
                <tr key={assignment.id}>
                  <td>
                    {assignment.desktop_image?.icon && assignment.desktop_image.icon.startsWith('/api/') ? (
                      <img src={assignment.desktop_image.icon} alt={assignment.desktop_image.name} className="icon-image" style={{ width: '24px', height: '24px', marginRight: '8px', verticalAlign: 'middle' }} />
                    ) : (
                      <span className="icon">{assignment.desktop_image?.icon}</span>
                    )}
                    {assignment.desktop_image?.name}
                  </td>
                  <td>
                    {assignment.group ? (
                      <span className="badge badge-group">👥 {assignment.group.name}</span>
                    ) : assignment.assigned_user ? (
                      <span className="badge badge-user">👤 {assignment.assigned_user.username}</span>
                    ) : (
                      <span className="badge">Unknown</span>
                    )}
                  </td>
                  <td>
                    {assignment.assignment_folder_name ? (
                      <div>
                        <strong>{assignment.assignment_folder_name}</strong>
                        <br />
                        <small className="path">{assignment.assignment_folder_path}</small>
                      </div>
                    ) : (
                      <span className="text-muted">No folder</span>
                    )}
                  </td>
                  <td>{new Date(assignment.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => openEditModal(assignment)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDeleteAssignment(assignment)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Assignment Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Assignment</h2>
            <form onSubmit={handleCreateAssignment}>
              <div className="form-group">
                <label>Desktop Image *</label>
                <select
                  value={formData.desktop_image_id}
                  onChange={(e) => setFormData({ ...formData, desktop_image_id: e.target.value })}
                  required
                >
                  <option value="">Select an image...</option>
                  {desktopImages.map((img) => (
                    <option key={img.id} value={img.id}>
                      {img.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Assign to Groups (optional)</label>
                <select
                  multiple
                  value={formData.group_ids.map(String)}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions).map(opt => parseInt(opt.value));
                    setFormData({ ...formData, group_ids: selected });
                  }}
                  size={5}
                  style={{ minHeight: '100px' }}
                >
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </select>
                <small className="help-text">Hold Ctrl/Cmd to select multiple groups</small>
              </div>

              <div className="form-group">
                <label>Assign to Individual Users (optional)</label>
                <select
                  multiple
                  value={formData.user_ids}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions).map(opt => opt.value);
                    setFormData({ ...formData, user_ids: selected });
                  }}
                  onFocus={() => users.length === 0 && loadUsers()}
                  size={5}
                  style={{ minHeight: '100px' }}
                >
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.username} ({user.email})
                    </option>
                  ))}
                </select>
                <small className="help-text">Hold Ctrl/Cmd to select multiple users</small>
              </div>

              <div className="form-group">
                <label>Assignment Folder (optional)</label>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowFolderBrowser(true);
                      loadBrowserFiles('');
                    }}
                  >
                    📁 Browse Folders
                  </button>
                  {selectedFolder && (
                    <div style={{ flex: 1 }}>
                      <strong>{selectedFolder.split('/').pop()}</strong>
                      <br />
                      <small className="path">{selectedFolder}</small>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        onClick={() => setSelectedFolder(null)}
                        style={{ marginLeft: '10px' }}
                      >
                        Clear
                      </button>
                    </div>
                  )}
                  {!selectedFolder && (
                    <span className="text-muted">No folder selected</span>
                  )}
                </div>
                <small className="help-text">
                  Selected folder will be mounted at: /home/kasm-user/public/[folder-name]
                </small>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Assignment Modal */}
      {showEditModal && selectedAssignment && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Assignment</h2>
            <form onSubmit={handleUpdateAssignment}>
              <div className="form-group">
                <label>Desktop Image</label>
                <div className="readonly-field">
                  {selectedAssignment.desktop_image?.icon && selectedAssignment.desktop_image.icon.startsWith('/api/') ? (
                    <img src={selectedAssignment.desktop_image.icon} alt={selectedAssignment.desktop_image.name} className="icon-image" style={{ width: '20px', height: '20px', marginRight: '8px', verticalAlign: 'middle' }} />
                  ) : (
                    <span>{selectedAssignment.desktop_image?.icon}</span>
                  )}
                  {selectedAssignment.desktop_image?.name}
                </div>
              </div>

              <div className="form-group">
                <label>Assigned To</label>
                <div className="readonly-field">
                  {selectedAssignment.group?.name || selectedAssignment.assigned_user?.username}
                </div>
              </div>

              <div className="form-group">
                <label>Assignment Folder (optional)</label>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowFolderBrowser(true);
                      loadBrowserFiles('');
                    }}
                  >
                    📁 Browse Folders
                  </button>
                  {selectedFolder && (
                    <div style={{ flex: 1 }}>
                      <strong>{selectedFolder.split('/').pop()}</strong>
                      <br />
                      <small className="path">{selectedFolder}</small>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        onClick={() => setSelectedFolder(null)}
                        style={{ marginLeft: '10px' }}
                      >
                        Clear
                      </button>
                    </div>
                  )}
                  {!selectedFolder && (
                    <span className="text-muted">No folder selected</span>
                  )}
                </div>
                <small className="help-text">
                  Selected folder will be mounted at: /home/kasm-user/public/[folder-name]
                </small>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Update Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Folder Browser Modal */}
      {showFolderBrowser && (
        <div className="modal-overlay" onClick={() => setShowFolderBrowser(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>📁 Select Folder from Your Private Space</h2>
            
            <div className="folder-browser">
              <div className="breadcrumb" style={{ marginBottom: '15px' }}>
                <button 
                  onClick={() => {
                    setCurrentBrowserPath('');
                    loadBrowserFiles('');
                  }} 
                  className="breadcrumb-item"
                >
                  🏠 Home
                </button>
                {currentBrowserPath.split('/').filter(p => p).map((part, index, arr) => {
                  const path = arr.slice(0, index + 1).join('/');
                  return (
                    <React.Fragment key={path}>
                      <span className="breadcrumb-separator">/</span>
                      <button 
                        onClick={() => {
                          setCurrentBrowserPath(path);
                          loadBrowserFiles(path);
                        }} 
                        className="breadcrumb-item"
                      >
                        {part}
                      </button>
                    </React.Fragment>
                  );
                })}
              </div>

              {loadingBrowser ? (
                <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>
              ) : browserFiles.length === 0 ? (
                <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                  No folders in this directory
                </div>
              ) : (
                <div className="folder-list" style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px' }}>
                  {browserFiles.map((folder) => (
                    <div
                      key={folder.path}
                      className="folder-item"
                      style={{
                        padding: '12px',
                        borderBottom: '1px solid #eee',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = '#f5f5f5'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <div
                        onClick={() => {
                          setCurrentBrowserPath(folder.path);
                          loadBrowserFiles(folder.path);
                        }}
                        style={{ flex: 1 }}
                      >
                        📁 {folder.name}
                      </div>
                      <button
                        type="button"
                        className="btn btn-sm btn-primary"
                        onClick={() => {
                          setSelectedFolder(folder.path);
                          setShowFolderBrowser(false);
                        }}
                      >
                        Select
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="modal-actions" style={{ marginTop: '15px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowFolderBrowser(false)}
              >
                Cancel
              </button>
              {currentBrowserPath && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setSelectedFolder(currentBrowserPath);
                    setShowFolderBrowser(false);
                  }}
                >
                  Select Current Folder
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && assignmentToDelete && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Delete Assignment</h2>
              <button className="modal-close" onClick={() => setShowDeleteModal(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete this assignment?</p>
              <div style={{ marginTop: '15px', padding: '15px', background: '#f5f5f5', borderRadius: '4px' }}>
                <strong>Desktop:</strong> {assignmentToDelete.desktop_image?.name}
                <br />
                <strong>Assigned to:</strong>{' '}
                {assignmentToDelete.group?.name || assignmentToDelete.assigned_user?.username}
                {assignmentToDelete.assignment_folder_name && (
                  <>
                    <br />
                    <strong>Folder:</strong> {assignmentToDelete.assignment_folder_name}
                  </>
                )}
              </div>
              <p style={{ marginTop: '15px', color: '#d32f2f' }}>
                <strong>Warning:</strong> This action cannot be undone.
              </p>
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
                onClick={confirmDeleteAssignment}
              >
                Delete Assignment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AssignmentManager;
