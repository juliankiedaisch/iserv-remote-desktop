from flask import Blueprint, jsonify, request, current_app
from app import db
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.users import User
from app.models.groups import Group
from app.middlewares.auth import require_auth
from app.i18n import get_message, get_language_from_request
import os

teacher_bp = Blueprint('teacher', __name__, url_prefix='/api/teacher')


def require_teacher(f):
    """Decorator to require teacher or admin role"""
    @require_auth
    def wrapper(user, *args, **kwargs):
        lang = get_language_from_request()
        if not (user.get('role') == 'teacher' or user.get('role') == 'admin'):
            return jsonify({'success': False, 'error': get_message('teacher_required', lang)}), 403
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
    lang = get_language_from_request()
    
    try:
        # Optional: filter by group_id
        group_id = request.args.get('group_id', type=int)
        
        if group_id:
            group = Group.query.get(group_id)
            if not group:
                return jsonify({'success': False, 'error': get_message('group_not_found', lang)}), 404
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
            assignments = DesktopAssignment.get_by_teacher(user['user_id'])
        
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
    """Create a new assignment for multiple groups and/or users"""
    lang = get_language_from_request()
    
    try:
        data = request.json
        
        # Validation
        if not data.get('desktop_image_id'):
            return jsonify({'success': False, 'error': get_message('desktop_image_id_required', lang)}), 400
        
        # Get group_ids and user_ids arrays
        group_ids = data.get('group_ids', [])
        user_ids = data.get('user_ids', [])
        
        # Must have at least one group or user
        if not group_ids and not user_ids:
            return jsonify({'success': False, 'error': get_message('at_least_one_group_or_user', lang)}), 400
        
        # Check if desktop image exists
        desktop_image = DesktopImage.query.get(data['desktop_image_id'])
        if not desktop_image:
            return jsonify({'success': False, 'error': get_message('desktop_type_not_found', lang)}), 404
        
        # Validate and prepare folder path
        folder_path = data.get('assignment_folder_path') or ''
        folder_path = folder_path.strip() if folder_path else ''
        folder_name = None
        
        current_app.logger.info(f"Received folder_path: '{folder_path}' (type: {type(folder_path)})")
        
        if folder_path:
            # Prevent directory traversal
            if '..' in folder_path or folder_path.startswith('/'):
                return jsonify({'success': False, 'error': get_message('invalid_folder_path', lang)}), 400
            
            # Extract folder name from path
            folder_name = folder_path.split('/')[-1]
            
            # Validate folder exists in teacher's private space
            user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
            teacher_private_path = os.path.join(
                user_data_base,
                user['user_id'],
                'PRIVATE',
                folder_path
            )
            
            current_app.logger.info(f"Checking folder at: {teacher_private_path}")
            current_app.logger.info(f"Folder exists: {os.path.exists(teacher_private_path)}")
            current_app.logger.info(f"Is directory: {os.path.isdir(teacher_private_path) if os.path.exists(teacher_private_path) else 'N/A'}")
            
            if not os.path.exists(teacher_private_path) or not os.path.isdir(teacher_private_path):
                return jsonify({'success': False, 'error': get_message('folder_not_exist', lang)}), 404
        
        created_assignments = []
        
        # Get description
        description = data.get('description', '').strip() if data.get('description') else None
        
        # Create assignments for each group
        for group_id in group_ids:
            assignment = DesktopAssignment(
                desktop_image_id=data['desktop_image_id'],
                group_id=group_id,
                user_id=None,
                description=description,
                assignment_folder_path=folder_path if folder_path else None,
                assignment_folder_name=folder_name,
                created_by=user['user_id']
            )
            db.session.add(assignment)
            created_assignments.append(assignment)
        
        # Create assignments for each user
        for user_id in user_ids:
            assignment = DesktopAssignment(
                desktop_image_id=data['desktop_image_id'],
                group_id=None,
                user_id=user_id,
                description=description,
                assignment_folder_path=folder_path if folder_path else None,
                assignment_folder_name=folder_name,
                created_by=user['user_id']
            )
            db.session.add(assignment)
            created_assignments.append(assignment)
        
        db.session.commit()
        
        # Reload assignments from database to ensure relationships are properly loaded
        assignment_ids = [a.id for a in created_assignments]
        reloaded_assignments = []
        for assignment_id in assignment_ids:
            assignment = DesktopAssignment.query.get(assignment_id)
            if assignment:
                reloaded_assignments.append(assignment)
        
        response = {
            'success': True,
            'created': len(reloaded_assignments),
            'assignments': [a.to_dict(include_relations=True) for a in reloaded_assignments]
        }
        
        return jsonify(response), 201
        
    except Exception as e:
        db.session.rollback()
        import traceback
        current_app.logger.error(f"Failed to create assignment: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_bp.route('/assignments/<int:assignment_id>', methods=['GET'])
@require_teacher
def get_assignment(user, assignment_id):
    """Get assignment details"""
    lang = get_language_from_request()
    
    try:
        assignment = DesktopAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': get_message('assignment_not_found', lang)}), 404
        
        # Teachers can only see their own assignments
        if user.get('role') == 'teacher' and assignment.created_by != user['user_id']:
            return jsonify({'success': False, 'error': get_message('unauthorized', lang)}), 403
        
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
    lang = get_language_from_request()
    
    try:
        assignment = DesktopAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': get_message('assignment_not_found', lang)}), 404
        
        # Teachers can only edit their own assignments
        if user.get('role') == 'teacher' and assignment.created_by != user['user_id']:
            return jsonify({'success': False, 'error': get_message('unauthorized', lang)}), 403
        
        data = request.json
        
        # Update description
        if 'description' in data:
            assignment.description = data['description'].strip() if data['description'] else None
        
        # Update folder path
        if 'assignment_folder_path' in data:
            folder_path = data['assignment_folder_path'].strip() if data['assignment_folder_path'] else None
            if folder_path:
                # Validate
                if '..' in folder_path or folder_path.startswith('/'):
                    return jsonify({'success': False, 'error': get_message('invalid_folder_path', lang)}), 400
            assignment.assignment_folder_path = folder_path
        
        # Update folder name
        if 'assignment_folder_name' in data:
            assignment.assignment_folder_name = data['assignment_folder_name']
        
        # Update group_ids if provided
        if 'group_ids' in data:
            new_group_ids = data.get('group_ids', [])
            new_user_ids = data.get('user_ids', [])
            
            if not new_group_ids and not new_user_ids:
                return jsonify({'success': False, 'error': get_message('at_least_one_group_or_user', lang)}), 400
            
            # For simplicity, update the existing assignment's target
            # If multiple groups/users provided, keep first in this assignment
            if new_group_ids:
                assignment.group_id = new_group_ids[0]
                assignment.user_id = None
            elif new_user_ids:
                assignment.user_id = new_user_ids[0]
                assignment.group_id = None
        elif 'user_ids' in data:
            new_user_ids = data.get('user_ids', [])
            new_group_ids = data.get('group_ids', [])
            
            if not new_group_ids and not new_user_ids:
                return jsonify({'success': False, 'error': get_message('at_least_one_group_or_user', lang)}), 400
            
            if new_user_ids:
                assignment.user_id = new_user_ids[0]
                assignment.group_id = None
            elif new_group_ids:
                assignment.group_id = new_group_ids[0]
                assignment.user_id = None
        
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
    lang = get_language_from_request()
    
    try:
        assignment = DesktopAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': get_message('assignment_not_found', lang)}), 404
        
        # Teachers can only delete their own assignments
        if user.get('role') == 'teacher' and assignment.created_by != user['user_id']:
            return jsonify({'success': False, 'error': get_message('unauthorized', lang)}), 403
        
        db.session.delete(assignment)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete assignment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
