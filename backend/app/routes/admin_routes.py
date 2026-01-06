from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.containers import Container
from app.models.users import User
from app.middlewares.auth import require_admin, require_oauth_admin
from app.services.docker_manager import DockerManager
from app.i18n import get_message

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/containers', methods=['GET'])
@require_admin
def list_all_containers(oauth_session, lang):
    """List all containers from all users (admin only)"""
    try:
        # Get all containers
        containers = Container.query.order_by(Container.created_at.desc()).all()
        
        # Get Docker manager to check real-time status
        docker_manager = DockerManager()
        
        container_list = []
        for container in containers:
            # Get user info
            user = User.query.get(container.user_id)
            
            # Get real-time status
            status = docker_manager.get_container_status(container)
            url = docker_manager.get_container_url(container)
            
            container_info = container.to_dict()
            container_info['username'] = user.username if user else 'Unknown'
            container_info['status'] = status.get('status', container.status)
            container_info['url'] = url
            
            container_list.append(container_info)
        
        return jsonify({
            'success': True,
            'containers': container_list
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to list all containers: {str(e)}")
        return jsonify({
            'success': False,
            'error': get_message('error_occurred', lang)
        }), 500


@admin_bp.route('/admin/container/<container_id>/stop', methods=['POST'])
@require_admin
def stop_container_admin(oauth_session, lang, container_id):
    """Stop a specific container (admin only)"""
    try:
        container = Container.query.get(container_id)
        
        if not container:
            return jsonify({
                'success': False,
                'error': get_message('container_not_found', lang)
            }), 404
        
        # Stop the container
        docker_manager = DockerManager()
        docker_manager.stop_container(container)
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} stopped container {container.container_name}"
        )
        
        return jsonify({
            'success': True,
            'message': get_message('container_stopped', lang)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to stop container: {str(e)}")
        return jsonify({
            'success': False,
            'error': get_message('failed_to_stop_container', lang)
        }), 500


@admin_bp.route('/admin/container/<container_id>/remove', methods=['DELETE'])
@require_admin
def remove_container_admin(oauth_session, lang, container_id):
    """Remove a specific container (admin only)"""
    try:
        container = Container.query.get(container_id)
        
        if not container:
            return jsonify({
                'success': False,
                'error': get_message('container_not_found', lang)
            }), 404
        
        # Remove the container
        docker_manager = DockerManager()
        docker_manager.remove_container(container)
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} removed container {container.container_name}"
        )
        
        return jsonify({
            'success': True,
            'message': get_message('container_removed', lang)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to remove container: {str(e)}")
        return jsonify({
            'success': False,
            'error': get_message('failed_to_remove_container', lang)
        }), 500


@admin_bp.route('/admin/containers/stop-all', methods=['POST'])
@require_admin
def stop_all_containers(oauth_session, lang):
    """Stop all running containers (admin only)"""
    try:
        # Get all running containers
        running_containers = Container.query.filter_by(status='running').all()
        
        docker_manager = DockerManager()
        stopped_count = 0
        
        for container in running_containers:
            try:
                docker_manager.stop_container(container)
                stopped_count += 1
            except Exception as e:
                current_app.logger.error(
                    f"Failed to stop container {container.container_name}: {str(e)}"
                )
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} stopped {stopped_count} containers"
        )
        
        return jsonify({
            'success': True,
            'message': get_message('containers_stopped', lang, count=stopped_count),
            'stopped_count': stopped_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to stop all containers: {str(e)}")
        return jsonify({
            'success': False,
            'error': get_message('error_occurred', lang)
        }), 500


@admin_bp.route('/admin/containers/cleanup-stopped', methods=['POST'])
@require_admin
def cleanup_stopped_containers(oauth_session, lang):
    """Remove all stopped containers (admin only)"""
    try:
        docker_manager = DockerManager()
        
        # Get all stopped containers
        stopped_containers = Container.query.filter_by(status='stopped').all()
        
        removed_count = 0
        for container in stopped_containers:
            try:
                docker_manager.remove_container(container)
                removed_count += 1
            except Exception as e:
                current_app.logger.error(
                    f"Failed to remove container {container.container_name}: {str(e)}"
                )
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} removed {removed_count} stopped containers"
        )
        
        return jsonify({
            'success': True,
            'message': get_message('containers_removed', lang, count=removed_count),
            'removed_count': removed_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to cleanup stopped containers: {str(e)}")
        return jsonify({
            'success': False,
            'error': get_message('error_occurred', lang)
        }), 500


@admin_bp.route('/admin/users', methods=['GET'])
@require_oauth_admin
def list_all_users(oauth_session, lang):
    """List all users with their groups and assignments (OAuth admin only)"""
    try:
        from app.models.desktop_assignments import DesktopAssignment
        
        # Get all users
        users = User.query.order_by(User.username).all()
        
        user_list = []
        for user in users:
            # Get user's assignments
            user_group_ids = [g.id for g in user.groups]
            assignments = DesktopAssignment.get_user_assignments(user.id, user_group_ids)
            
            user_info = user.to_dict()
            user_info['assignments'] = [assignment.to_dict(include_relations=True) for assignment in assignments]
            user_info['assignment_count'] = len(assignments)
            
            user_list.append(user_info)
        
        return jsonify({
            'success': True,
            'users': user_list
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to list all users: {str(e)}")
        return jsonify({
            'success': False,
            'error': get_message('error_occurred', lang)
        }), 500


@admin_bp.route('/admin/user/<user_id>/role', methods=['PUT'])
@require_oauth_admin
def update_user_role(oauth_session, lang, user_id):
    """Update a user's role override (OAuth admin only)"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': get_message('user_not_found', lang)
            }), 404
        
        # Get the new role from request
        data = request.get_json()
        new_role = data.get('role')
        
        # Validate role
        valid_roles = ['admin', 'teacher', 'student', None]
        if new_role not in valid_roles:
            return jsonify({
                'success': False,
                'error': 'Invalid role. Must be one of: admin, teacher, student, or null to remove override.'
            }), 400
        
        # Update role override
        if new_role is None:
            # Remove override, revert to OAuth role
            user.role_override = None
            user.role = user.get_oauth_role()
        else:
            # Set override
            user.role_override = new_role
            user.role = new_role
        
        db.session.commit()
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} updated role for user {user.username} to {new_role}"
        )
        
        return jsonify({
            'success': True,
            'message': get_message('user_role_updated', lang),
            'user': user.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to update user role: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': get_message('error_occurred', lang)
        }), 500
