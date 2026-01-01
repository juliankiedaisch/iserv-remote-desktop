from flask import Blueprint, jsonify, request, current_app
from app import db
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.users import User
from app.models.groups import Group
from app.middlewares.auth import require_auth

teacher_bp = Blueprint('teacher', __name__, url_prefix='/api/teacher')


def require_teacher(f):
    """Decorator to require teacher or admin role"""
    @require_auth
    def wrapper(user, *args, **kwargs):
        if not (user.get('role') == 'teacher' or user.get('role') == 'admin'):
            return jsonify({'success': False, 'error': 'Teacher or admin role required'}), 403
        return f(user, *args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@teacher_bp.route('/desktop-images', methods=['GET'])
@require_teacher
def list_available_images(user):
    """List all available desktop images for assignment"""
    try:
        images = DesktopImage.query.filter_by(enabled=True).all()
        return jsonify({
            'success': True,
            'images': [img.to_dict() for img in images]
        })
    except Exception as e:
        current_app.logger.error(f"Failed to list desktop images: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/groups', methods=['GET'])
@require_teacher
def list_groups(user):
    """List all groups for assignment"""
    try:
        groups = Group.query.all()
        return jsonify({
            'success': True,
            'groups': [g.to_dict() for g in groups]
        })
    except Exception as e:
        current_app.logger.error(f"Failed to list groups: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/users', methods=['GET'])
@require_teacher
def list_users(user):
    """List all users for assignment"""
    try:
        # Optional: filter by group_id
        group_id = request.args.get('group_id', type=int)
        
        if group_id:
            group = Group.query.get(group_id)
            if not group:
                return jsonify({'success': False, 'error': 'Group not found'}), 404
            users = group.members
        else:
            users = User.query.all()
        
        return jsonify({
            'success': True,
            'users': [{
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role
            } for u in users]
        })
    except Exception as e:
        current_app.logger.error(f"Failed to list users: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/assignments', methods=['GET'])
@require_teacher
def list_assignments(user):
    """List assignments created by this teacher (or all if admin)"""
    try:
        if user.get('role') == 'admin':
            # Admins see all assignments
            assignments = DesktopAssignment.query.all()
        else:
            # Teachers see only their own
            assignments = DesktopAssignment.get_by_teacher(user['id'])
        
        return jsonify({
            'success': True,
            'assignments': [a.to_dict(include_relations=True) for a in assignments]
        })
    except Exception as e:
        current_app.logger.error(f"Failed to list assignments: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/assignments', methods=['POST'])
@require_teacher
def create_assignment(user):
    """Create a new assignment"""
    try:
        data = request.json
        
        # Validation
        if not data.get('desktop_image_id'):
            return jsonify({'success': False, 'error': 'desktop_image_id is required'}), 400
        
        # Must have either group_id or user_id, but not both
        has_group = data.get('group_id') is not None
        has_user = data.get('user_id') is not None
        
        if not has_group and not has_user:
            return jsonify({'success': False, 'error': 'Either group_id or user_id is required'}), 400
        
        if has_group and has_user:
            return jsonify({'success': False, 'error': 'Cannot specify both group_id and user_id'}), 400
        
        # Check if desktop image exists
        desktop_image = DesktopImage.query.get(data['desktop_image_id'])
        if not desktop_image:
            return jsonify({'success': False, 'error': 'Desktop image not found'}), 404
        
        # Check for duplicate assignment
        if has_group:
            existing = DesktopAssignment.query.filter_by(
                desktop_image_id=data['desktop_image_id'],
                group_id=data['group_id']
            ).first()
            if existing:
                return jsonify({'success': False, 'error': 'Assignment already exists for this group'}), 400
        
        if has_user:
            existing = DesktopAssignment.query.filter_by(
                desktop_image_id=data['desktop_image_id'],
                user_id=data['user_id']
            ).first()
            if existing:
                return jsonify({'success': False, 'error': 'Assignment already exists for this user'}), 400
        
        # Validate folder path if provided
        folder_path = data.get('assignment_folder_path', '').strip()
        if folder_path:
            # Prevent directory traversal
            if '..' in folder_path or folder_path.startswith('/'):
                return jsonify({'success': False, 'error': 'Invalid folder path'}), 400
            
            # Ensure it starts with assignments/
            if not folder_path.startswith('assignments/'):
                folder_path = f'assignments/{folder_path}'
        
        # Create assignment
        assignment = DesktopAssignment(
            desktop_image_id=data['desktop_image_id'],
            group_id=data.get('group_id'),
            user_id=data.get('user_id'),
            assignment_folder_path=folder_path if folder_path else None,
            assignment_folder_name=data.get('assignment_folder_name'),
            created_by=user['id']
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'assignment': assignment.to_dict(include_relations=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create assignment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/assignments/<int:assignment_id>', methods=['GET'])
@require_teacher
def get_assignment(user, assignment_id):
    """Get assignment details"""
    try:
        assignment = DesktopAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        # Teachers can only see their own assignments
        if user.get('role') == 'teacher' and assignment.created_by != user['id']:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        return jsonify({
            'success': True,
            'assignment': assignment.to_dict(include_relations=True)
        })
    except Exception as e:
        current_app.logger.error(f"Failed to get assignment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/assignments/<int:assignment_id>', methods=['PUT'])
@require_teacher
def update_assignment(user, assignment_id):
    """Update an assignment"""
    try:
        assignment = DesktopAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        # Teachers can only edit their own assignments
        if user.get('role') == 'teacher' and assignment.created_by != user['id']:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        data = request.json
        
        # Update folder path
        if 'assignment_folder_path' in data:
            folder_path = data['assignment_folder_path'].strip() if data['assignment_folder_path'] else None
            if folder_path:
                # Validate
                if '..' in folder_path or folder_path.startswith('/'):
                    return jsonify({'success': False, 'error': 'Invalid folder path'}), 400
                if not folder_path.startswith('assignments/'):
                    folder_path = f'assignments/{folder_path}'
            assignment.assignment_folder_path = folder_path
        
        # Update folder name
        if 'assignment_folder_name' in data:
            assignment.assignment_folder_name = data['assignment_folder_name']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'assignment': assignment.to_dict(include_relations=True)
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update assignment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/assignments/<int:assignment_id>', methods=['DELETE'])
@require_teacher
def delete_assignment(user, assignment_id):
    """Delete an assignment"""
    try:
        assignment = DesktopAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        # Teachers can only delete their own assignments
        if user.get('role') == 'teacher' and assignment.created_by != user['id']:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        db.session.delete(assignment)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete assignment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
