"""
Admin routes for managing desktop types and assignments
"""
from flask import Blueprint, request, jsonify
from functools import wraps
from app import db
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.users import User
from app.middlewares.auth import require_auth

desktop_admin_bp = Blueprint('desktop_admin', __name__, url_prefix='/api/admin/desktops')


def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    @require_auth
    def decorated_function(user, *args, **kwargs):
        # user is a dict with keys: session_id, user_id, username, email, role
        if not user or user.get('role') != 'admin':
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        return f(user, *args, **kwargs)
    
    return decorated_function


@desktop_admin_bp.route('/types', methods=['GET'])
@require_admin
def list_desktop_types(user):
    """List all desktop types"""
    desktop_types = DesktopImage.query.all()
    
    # Include assignment counts
    result = []
    for dt in desktop_types:
        dt_dict = dt.to_dict()
        dt_dict['assignment_count'] = len(dt.assignments)
        result.append(dt_dict)
    
    return jsonify({"success": True, "desktop_types": result})


@desktop_admin_bp.route('/types', methods=['POST'])
@require_admin
def create_desktop_type(user):
    """Create new desktop type"""
    data = request.json
    
    # Validate required fields
    if not data.get('name') or not data.get('docker_image'):
        return jsonify({"success": False, "error": "Name and docker_image are required"}), 400
    
    # Check if name already exists
    existing = DesktopImage.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify({"success": False, "error": "Desktop type with this name already exists"}), 400
    
    desktop_type = DesktopImage(
        name=data['name'],
        docker_image=data['docker_image'],
        description=data.get('description'),
        icon=data.get('icon', '🖥️'),
        enabled=data.get('enabled', True)
    )
    
    db.session.add(desktop_type)
    db.session.commit()
    
    return jsonify({"success": True, "desktop_type": desktop_type.to_dict()})


@desktop_admin_bp.route('/types/<int:type_id>', methods=['PUT'])
@require_admin
def update_desktop_type(user, type_id):
    """Update desktop type"""
    desktop_type = DesktopImage.query.get(type_id)
    if not desktop_type:
        return jsonify({"success": False, "error": "Desktop type not found"}), 404
    
    data = request.json
    
    # Update fields
    if 'name' in data:
        desktop_type.name = data['name']
    if 'docker_image' in data:
        desktop_type.docker_image = data['docker_image']
    if 'description' in data:
        desktop_type.description = data['description']
    if 'icon' in data:
        desktop_type.icon = data['icon']
    if 'enabled' in data:
        desktop_type.enabled = data['enabled']
    
    db.session.commit()
    
    return jsonify({"success": True, "desktop_type": desktop_type.to_dict()})


@desktop_admin_bp.route('/types/<int:type_id>', methods=['DELETE'])
@require_admin
def delete_desktop_type(user, type_id):
    """Delete desktop type"""
    desktop_type = DesktopImage.query.get(type_id)
    if not desktop_type:
        return jsonify({"success": False, "error": "Desktop type not found"}), 404
    
    db.session.delete(desktop_type)
    db.session.commit()
    
    return jsonify({"success": True})


@desktop_admin_bp.route('/types/<int:type_id>/assignments', methods=['GET'])
@require_admin
def list_assignments(user, type_id):
    """List assignments for a desktop type"""
    desktop_type = DesktopImage.query.get(type_id)
    if not desktop_type:
        return jsonify({"success": False, "error": "Desktop type not found"}), 404
    
    assignments = []
    for a in desktop_type.assignments:
        assignment_dict = a.to_dict()
        
        # If it's a user assignment, include the username
        if a.user_id:
            assigned_user = User.query.get(a.user_id)
            if assigned_user:
                assignment_dict['username'] = assigned_user.username
                assignment_dict['user_email'] = assigned_user.email
        
        assignments.append(assignment_dict)
    
    return jsonify({"success": True, "assignments": assignments})


@desktop_admin_bp.route('/types/<int:type_id>/assignments', methods=['POST'])
@require_admin
def create_assignment(user, type_id):
    """Create new assignment"""
    desktop_type = DesktopImage.query.get(type_id)
    if not desktop_type:
        return jsonify({"success": False, "error": "Desktop type not found"}), 404
    
    data = request.json
    
    # Validate: must have either group_id or user_id
    if not data.get('group_id') and not data.get('user_id'):
        return jsonify({"success": False, "error": "Either group_id or user_id is required"}), 400
    
    # Check for duplicate
    if data.get('group_id'):
        existing = DesktopAssignment.query.filter_by(
            desktop_image_id=type_id,
            group_id=data['group_id']
        ).first()
        if existing:
            return jsonify({"success": False, "error": "Assignment already exists"}), 400
    
    if data.get('user_id'):
        existing = DesktopAssignment.query.filter_by(
            desktop_image_id=type_id,
            user_id=data['user_id']
        ).first()
        if existing:
            return jsonify({"success": False, "error": "Assignment already exists"}), 400
    
    assignment = DesktopAssignment(
        desktop_image_id=type_id,
        group_id=data.get('group_id'),
        user_id=data.get('user_id'),
        assignment_folder_path=data.get('assignment_folder_path'),
        assignment_folder_name=data.get('assignment_folder_name'),
        created_by=user['id']  # Set the admin as creator
    )
    
    db.session.add(assignment)
    db.session.commit()
    
    return jsonify({"success": True, "assignment": assignment.to_dict()})


@desktop_admin_bp.route('/assignments/<int:assignment_id>', methods=['DELETE'])
@require_admin
def delete_assignment(user, assignment_id):
    """Delete assignment"""
    assignment = DesktopAssignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found"}), 404
    
    db.session.delete(assignment)
    db.session.commit()
    
    return jsonify({"success": True})


@desktop_admin_bp.route('/available-groups', methods=['GET'])
@require_admin
def get_available_groups(user):
    """Get list of available groups from users"""
    from sqlalchemy import func
    
    # Get unique groups from all users' user_data
    users_with_groups = User.query.filter(User.user_data.isnot(None)).all()
    
    groups_set = set()
    for u in users_with_groups:
        if u.user_data and 'groups' in u.user_data:
            if type(u.user_data.get('groups')) == dict:
                group_list = [elem.get("act", "") for elem in u.user_data.get('groups', {}).values()]
                groups_set.update(group_list)
            elif type(u.user_data.get('groups')) == list:
                groups_set.update(u.user_data.get('groups', []))
    
    # Remove empty strings and sort
    groups = sorted([g for g in groups_set if g])
    
    return jsonify({"success": True, "groups": groups})


@desktop_admin_bp.route('/available-users', methods=['GET'])
@require_admin
def get_available_users(user):
    """Get list of available users"""
    users = User.query.all()
    
    user_list = [{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role': u.role
    } for u in users]
    
    return jsonify({"success": True, "users": user_list})

