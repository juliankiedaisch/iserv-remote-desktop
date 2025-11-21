from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.oauth_session import OAuthSession
from app.models.containers import Container
from app.services.docker_manager import DockerManager
from datetime import datetime, timezone
from functools import wraps

container_bp = Blueprint('container', __name__)

def require_session(f):
    """Decorator to require valid session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get session ID from various sources
        session_id = request.args.get('session_id')
        
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            return jsonify({'error': 'No session ID provided'}), 400
        
        # Validate session
        oauth_session = OAuthSession.query.filter_by(id=session_id).first()
        if not oauth_session:
            return jsonify({'error': 'Invalid session'}), 401
        
        # Check if session is expired
        current_time = datetime.now(timezone.utc)
        expires_at = oauth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < current_time:
            return jsonify({'error': 'Session expired'}), 401
        
        # Update last accessed
        oauth_session.last_accessed = current_time
        db.session.commit()
        
        # Pass session to the route
        return f(oauth_session, *args, **kwargs)
    
    return decorated_function


@container_bp.route('/container/start', methods=['POST'])
@require_session
def start_container(oauth_session):
    """Start a new container for the user"""
    try:
        user = oauth_session.user
        
        # Check if user already has a running container for this session
        existing = Container.get_by_session(oauth_session.id)
        if existing:
            docker_manager = DockerManager()
            status = docker_manager.get_container_status(existing)
            
            if status['status'] == 'running':
                url = docker_manager.get_container_url(existing)
                return jsonify({
                    'success': True,
                    'message': 'Container already running',
                    'container': existing.to_dict(),
                    'url': url
                })
        
        # Create new container
        docker_manager = DockerManager()
        container = docker_manager.create_container(
            user_id=user.id,
            session_id=oauth_session.id,
            username=user.username
        )
        
        url = docker_manager.get_container_url(container)
        
        return jsonify({
            'success': True,
            'message': 'Container started successfully',
            'container': container.to_dict(),
            'url': url
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Failed to start container: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/status', methods=['GET'])
@require_session
def get_container_status(oauth_session):
    """Get status of user's container"""
    try:
        # Get container for this session
        container = Container.get_by_session(oauth_session.id)
        
        if not container:
            return jsonify({
                'success': True,
                'has_container': False,
                'message': 'No container for this session'
            })
        
        # Get current status from Docker
        docker_manager = DockerManager()
        status = docker_manager.get_container_status(container)
        url = docker_manager.get_container_url(container)
        
        return jsonify({
            'success': True,
            'has_container': True,
            'container': container.to_dict(),
            'status': status,
            'url': url
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get container status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/stop', methods=['POST'])
@require_session
def stop_container(oauth_session):
    """Stop user's container"""
    try:
        # Get container for this session
        container = Container.get_by_session(oauth_session.id)
        
        if not container:
            return jsonify({
                'success': False,
                'error': 'No running container found'
            }), 404
        
        # Stop the container
        docker_manager = DockerManager()
        docker_manager.stop_container(container)
        
        return jsonify({
            'success': True,
            'message': 'Container stopped successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to stop container: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/remove', methods=['POST', 'DELETE'])
@require_session
def remove_container(oauth_session):
    """Remove user's container"""
    try:
        # Get container for this session
        container = Container.query.filter_by(session_id=oauth_session.id).first()
        
        if not container:
            return jsonify({
                'success': False,
                'error': 'No container found'
            }), 404
        
        # Remove the container
        docker_manager = DockerManager()
        docker_manager.remove_container(container)
        
        return jsonify({
            'success': True,
            'message': 'Container removed successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to remove container: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/list', methods=['GET'])
@require_session
def list_containers(oauth_session):
    """List all containers for the user"""
    try:
        user = oauth_session.user
        
        # Get all containers for this user
        containers = Container.get_by_user(user.id)
        
        # Get current status for each
        docker_manager = DockerManager()
        container_list = []
        
        for container in containers:
            status = docker_manager.get_container_status(container)
            url = docker_manager.get_container_url(container)
            
            container_info = container.to_dict()
            container_info['status'] = status
            container_info['url'] = url
            container_list.append(container_info)
        
        return jsonify({
            'success': True,
            'containers': container_list
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to list containers: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
