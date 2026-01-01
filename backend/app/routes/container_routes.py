from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.oauth_session import OAuthSession
from app.models.containers import Container
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
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
        
        # Get desktop_type from query params or request body
        desktop_type = request.args.get('desktop_type')
        if not desktop_type:
            data = request.get_json() or {}
            desktop_type = data.get('desktop_type', 'ubuntu-desktop')
        
        # Check desktop type permissions
        desktop_type_record = DesktopImage.query.filter_by(name=desktop_type).first()
        
        if desktop_type_record:
            # If desktop type exists in database, check if it's enabled
            if not desktop_type_record.enabled:
                return jsonify({
                    'success': False,
                    'error': f'Desktop type "{desktop_type}" is currently disabled'
                }), 403
            
            # Check user permission
            user_groups = user.get_group_names()
            if not DesktopAssignment.check_access(desktop_type_record.id, user.id, user_groups):
                return jsonify({
                    'success': False,
                    'error': f'You do not have permission to access "{desktop_type}" desktops'
                }), 403
        # If desktop_type_record is None, it's a legacy desktop type - allow for backward compatibility
        
        # Check if user already has a running container for this desktop type
        existing = Container.query.filter_by(
            session_id=oauth_session.id,
            desktop_type=desktop_type,
            status='running'
        ).first()
        
        if existing:
            docker_manager = DockerManager()
            status = docker_manager.get_container_status(existing)
            
            if status['status'] == 'running':
                # Update last accessed time
                existing.last_accessed = datetime.now(timezone.utc)
                db.session.commit()
                
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
            username=user.username,
            desktop_type=desktop_type
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
        # Get desktop type from request
        data = request.get_json() or {}
        desktop_type = data.get('desktop_type') or request.args.get('desktop_type')
        
        current_app.logger.info(f"Stop request - session_id: {oauth_session.id}, desktop_type: {desktop_type}, user_id: {oauth_session.user_id}")
        
        # Get container for this session and desktop type
        # Since users can have multiple containers, we need to match by user_id and desktop_type
        if desktop_type:
            container = Container.query.filter_by(
                user_id=oauth_session.user_id,
                desktop_type=desktop_type,
                status='running'
            ).first()
            current_app.logger.info(f"Container query result: {container}")
        else:
            container = Container.get_by_session(oauth_session.id)
        
        if not container:
            # Log all containers for this user to help debug
            all_user_containers = Container.query.filter_by(user_id=oauth_session.user_id).all()
            current_app.logger.warning(f"No running container found. User has {len(all_user_containers)} total containers: {[c.desktop_type for c in all_user_containers]}")
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
        container = Container.get_by_session(oauth_session.id)
        
        if not container:
            # Also check for any stopped containers
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
    """List all containers for the user (only for assigned desktop images)"""
    try:
        user = oauth_session.user
        user_group_ids = [g.id for g in user.groups]
        
        # Get all containers for this user
        containers = Container.get_by_user(user.id)
        
        # Get current status for each
        docker_manager = DockerManager()
        container_list = []
        
        for container in containers:
            # Check if user still has access to this desktop image
            if container.desktop_image_id:
                has_access, _ = DesktopAssignment.check_access(container.desktop_image_id, user.id, user_group_ids)
                if not has_access:
                    # User no longer has access to this desktop image, skip this container
                    continue
            else:
                # Old container without desktop_image_id (from old structure), skip it
                continue
            
            status_info = docker_manager.get_container_status(container)
            url = docker_manager.get_container_url(container)
            
            container_info = container.to_dict()
            # Update status from actual Docker state
            container_info['status'] = status_info.get('status', container.status)
            container_info['docker_status'] = status_info.get('docker_status', 'unknown')
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


@container_bp.route('/container/available-types', methods=['GET'])
@require_session
def get_available_desktop_types(oauth_session):
    """Get list of desktop types available to the current user"""
    try:
        user = oauth_session.user
        user_group_ids = [g.id for g in user.groups]
        
        # Get all enabled desktop types
        all_types = DesktopImage.query.filter_by(enabled=True).all()
        
        available_types = []
        for desktop_type in all_types:
            # Check if user has access
            has_access, assignment = DesktopAssignment.check_access(desktop_type.id, user.id, user_group_ids)
            if has_access:
                desktop_data = {
                    'id': desktop_type.id,
                    'name': desktop_type.name,
                    'docker_image': desktop_type.docker_image,
                    'description': desktop_type.description,
                    'icon': desktop_type.icon
                }
                
                # Include assignment info if available
                if assignment:
                    desktop_data['assignment'] = {
                        'folder_path': assignment.assignment_folder_path,
                        'folder_name': assignment.assignment_folder_name
                    }
                
                available_types.append(desktop_data)
        
        return jsonify({
            'success': True,
            'desktop_types': available_types
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get available desktop types: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/health', methods=['GET'])
@require_session
def check_container_health(oauth_session):
    """Check if a specific container is ready and responding"""
    try:
        desktop_type = request.args.get('desktop_type')
        
        if not desktop_type:
            return jsonify({
                'success': False,
                'error': 'desktop_type parameter required'
            }), 400
        
        # Get container for this user and desktop type
        container = Container.query.filter_by(
            user_id=oauth_session.user_id,
            desktop_type=desktop_type,
            status='running'
        ).first()
        
        if not container:
            return jsonify({
                'success': False,
                'ready': False,
                'error': 'Container not found or not running'
            }), 404
        
        # Check Docker container status
        docker_manager = DockerManager()
        status_info = docker_manager.get_container_status(container)
        
        # Container is ready if Docker reports it as running
        is_ready = status_info.get('status') == 'running'
        
        return jsonify({
            'success': True,
            'ready': is_ready,
            'status': status_info.get('status'),
            'container_id': container.id
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to check container health: {str(e)}")
        return jsonify({
            'success': False,
            'ready': False,
            'error': str(e)
        }), 500
