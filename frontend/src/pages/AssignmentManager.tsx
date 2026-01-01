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
  const [selectedAssignment, setSelectedAssignment] = useState<Assignment | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    desktop_image_id: '',
    assignment_type: 'group', // 'group' or 'user'
    group_id: '',
    user_id: '',
    assignment_folder_path: '',
    assignment_folder_name: '',
  });

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

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = {
        desktop_image_id: parseInt(formData.desktop_image_id),
        assignment_folder_path: formData.assignment_folder_path || null,
        assignment_folder_name: formData.assignment_folder_name || null,
      };

      if (formData.assignment_type === 'group') {
        payload.group_id = parseInt(formData.group_id);
      } else {
        payload.user_id = formData.user_id;
      }

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
        assignment_folder_path: formData.assignment_folder_path || null,
        assignment_folder_name: formData.assignment_folder_name || null,
      });
      setShowEditModal(false);
      setSelectedAssignment(null);
      resetForm();
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to update assignment');
    }
  };

  const handleDeleteAssignment = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this assignment?')) return;

    try {
      await apiService.delete(`/api/teacher/assignments/${id}`);
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
      assignment_type: assignment.group_id ? 'group' : 'user',
      group_id: assignment.group_id?.toString() || '',
      user_id: assignment.user_id || '',
      assignment_folder_path: assignment.assignment_folder_path || '',
      assignment_folder_name: assignment.assignment_folder_name || '',
    });
    setShowEditModal(true);
  };

  const resetForm = () => {
    setFormData({
      desktop_image_id: '',
      assignment_type: 'group',
      group_id: '',
      user_id: '',
      assignment_folder_path: '',
      assignment_folder_name: '',
    });
  };

  const handleAssignmentTypeChange = (type: 'group' | 'user') => {
    setFormData({ ...formData, assignment_type: type, group_id: '', user_id: '' });
    if (type === 'user') {
      loadUsers();
    }
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
                    <span className="icon">{assignment.desktop_image?.icon}</span>
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
                      onClick={() => handleDeleteAssignment(assignment.id)}
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
                      {img.icon} {img.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Assignment Type *</label>
                <div className="radio-group">
                  <label>
                    <input
                      type="radio"
                      checked={formData.assignment_type === 'group'}
                      onChange={() => handleAssignmentTypeChange('group')}
                    />
                    Group
                  </label>
                  <label>
                    <input
                      type="radio"
                      checked={formData.assignment_type === 'user'}
                      onChange={() => handleAssignmentTypeChange('user')}
                    />
                    Individual User
                  </label>
                </div>
              </div>

              {formData.assignment_type === 'group' ? (
                <div className="form-group">
                  <label>Group *</label>
                  <select
                    value={formData.group_id}
                    onChange={(e) => setFormData({ ...formData, group_id: e.target.value })}
                    required
                  >
                    <option value="">Select a group...</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="form-group">
                  <label>User *</label>
                  <select
                    value={formData.user_id}
                    onChange={(e) => setFormData({ ...formData, user_id: e.target.value })}
                    required
                  >
                    <option value="">Select a user...</option>
                    {users.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.username} ({user.email})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="form-group">
                <label>Assignment Folder Name (optional)</label>
                <input
                  type="text"
                  placeholder="e.g., Math 101 Homework"
                  value={formData.assignment_folder_name}
                  onChange={(e) =>
                    setFormData({ ...formData, assignment_folder_name: e.target.value })
                  }
                />
              </div>

              <div className="form-group">
                <label>Assignment Folder Path (optional)</label>
                <input
                  type="text"
                  placeholder="e.g., math101 or assignments/math101"
                  value={formData.assignment_folder_path}
                  onChange={(e) =>
                    setFormData({ ...formData, assignment_folder_path: e.target.value })
                  }
                />
                <small className="help-text">
                  Path will be created at: /home/kasm-user/public/assignments/your-path
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
                  {selectedAssignment.desktop_image?.icon} {selectedAssignment.desktop_image?.name}
                </div>
              </div>

              <div className="form-group">
                <label>Assigned To</label>
                <div className="readonly-field">
                  {selectedAssignment.group?.name || selectedAssignment.assigned_user?.username}
                </div>
              </div>

              <div className="form-group">
                <label>Assignment Folder Name</label>
                <input
                  type="text"
                  placeholder="e.g., Math 101 Homework"
                  value={formData.assignment_folder_name}
                  onChange={(e) =>
                    setFormData({ ...formData, assignment_folder_name: e.target.value })
                  }
                />
              </div>

              <div className="form-group">
                <label>Assignment Folder Path</label>
                <input
                  type="text"
                  placeholder="e.g., math101 or assignments/math101"
                  value={formData.assignment_folder_path}
                  onChange={(e) =>
                    setFormData({ ...formData, assignment_folder_path: e.target.value })
                  }
                />
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
    </div>
  );
};

export default AssignmentManager;
