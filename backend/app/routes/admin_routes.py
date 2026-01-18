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


@admin_bp.route('/admin/containers/sync-database', methods=['POST'])
@require_admin
def sync_database(oauth_session, lang):
    """Synchronize database with Docker state and clean up inconsistencies (admin only)"""
    try:
        docker_manager = DockerManager()
        stats = docker_manager.sync_database_with_docker()
        
        if 'error' in stats:
            return jsonify({
                'success': False,
                'error': stats['error']
            }), 500
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} triggered database sync: "
            f"{stats['removed_orphaned']} orphaned, {stats['updated_status']} updated, "
            f"{stats['cleaned_stuck']} stuck, {stats['normalized_paths']} normalized"
        )
        
        return jsonify({
            'success': True,
            'message': 'Database synchronized with Docker',
            'stats': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to sync database: {str(e)}")
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
        
        # Prevent overriding OAuth admin roles
        if user.get_oauth_role() == 'admin':
            return jsonify({
                'success': False,
                'error': 'Cannot override OAuth admin role. Users with admin privileges from IServ cannot have their role changed.'
            }), 403
        
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


@admin_bp.route('/admin/container/<container_id>/config/reset', methods=['POST'])
@require_admin
def reset_container_config(oauth_session, lang, container_id):
    """Reset config for a specific container (admin only)"""
    try:
        container = Container.query.get(container_id)
        
        if not container:
            return jsonify({
                'success': False,
                'error': get_message('container_not_found', lang)
            }), 404
        
        # Reset config for the container's user and image
        docker_manager = DockerManager()
        result = docker_manager.reset_user_config(container.user_id, container.image_name)
        
        if result['success']:
            current_app.logger.info(
                f"Admin {oauth_session.user.username} reset config for container {container.container_name} "
                f"(user: {container.user_id}, image: {container.image_name})"
            )
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.error(f"Failed to reset container config: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/admin/containers/config/reset-bulk', methods=['POST'])
@require_admin
def reset_containers_config_bulk(oauth_session, lang):
    """Reset config for multiple containers (admin only)"""
    try:
        data = request.get_json() or {}
        container_ids = data.get('container_ids', [])
        
        if not container_ids or not isinstance(container_ids, list):
            return jsonify({
                'success': False,
                'error': 'container_ids must be provided as an array'
            }), 400
        
        docker_manager = DockerManager()
        results = []
        success_count = 0
        error_count = 0
        
        for container_id in container_ids:
            container = Container.query.get(container_id)
            
            if not container:
                results.append({
                    'container_id': container_id,
                    'success': False,
                    'error': 'Container not found'
                })
                error_count += 1
                continue
            
            # Reset config for this container
            result = docker_manager.reset_user_config(container.user_id, container.image_name)
            results.append({
                'container_id': container_id,
                'container_name': container.container_name,
                'user_id': container.user_id,
                'image_name': container.image_name,
                'success': result['success'],
                'message': result.get('message'),
                'error': result.get('error')
            })
            
            if result['success']:
                success_count += 1
            else:
                error_count += 1
        
        current_app.logger.info(
            f"Admin {oauth_session.user.username} performed bulk config reset: "
            f"{success_count} succeeded, {error_count} failed"
        )
        
        return jsonify({
            'success': True,
            'message': f'Reset {success_count} config(s) successfully, {error_count} failed',
            'success_count': success_count,
            'error_count': error_count,
            'results': results
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to perform bulk config reset: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
