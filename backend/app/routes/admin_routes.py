from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.oauth_session import OAuthSession
from app.models.containers import Container
from app.models.users import User
from app.services.docker_manager import DockerManager
from app.i18n import get_message, get_language_from_request
from datetime import datetime, timezone
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        lang = get_language_from_request()
        
        # Get session ID from various sources
        session_id = request.args.get('session_id')
        
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            return jsonify({'error': get_message('session_required', lang)}), 400
        
        # Validate session
        oauth_session = OAuthSession.query.filter_by(id=session_id).first()
        if not oauth_session:
            return jsonify({'error': get_message('invalid_session', lang)}), 401
        
        # Check if session is expired
        current_time = datetime.now(timezone.utc)
        expires_at = oauth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < current_time:
            return jsonify({'error': get_message('invalid_session', lang)}), 401
        
        # Check if user is admin
        user = oauth_session.user
        if not user.is_admin:
            return jsonify({'error': get_message('admin_required', lang)}), 403
        
        # Update last accessed
        oauth_session.last_accessed = current_time
        db.session.commit()
        
        # Pass session and language to the route
        return f(oauth_session, lang, *args, **kwargs)
    
    return decorated_function


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
