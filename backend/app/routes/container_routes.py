from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.oauth_session import OAuthSession
from app.models.containers import Container
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.services.docker_manager import DockerManager
from app.services.container_queue import get_container_queue, ContainerCreationRequest
from app.i18n import get_message, get_language_from_request
from app.middlewares.auth import require_auth
from datetime import datetime, timezone
import os

container_bp = Blueprint('container', __name__)


@container_bp.route('/container/start', methods=['POST'])
@require_auth
def start_container(user_dict):
    """Start a new container for the user"""
    lang = get_language_from_request()
    
    try:
        # Get oauth_session from request context (set by require_auth)
        oauth_session = request.oauth_session
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
                    'error': get_message('desktop_type_disabled', lang, desktop_type=desktop_type)
                }), 403
            
            # Check user permission
            user_groups = user.get_group_names()
            if not DesktopAssignment.check_access(desktop_type_record.id, user.id, user_groups):
                return jsonify({
                    'success': False,
                    'error': get_message('no_desktop_permission', lang, desktop_type=desktop_type)
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
                    'message': get_message('container_already_running', lang),
                    'container': existing.to_dict(),
                    'url': url
                })
        
        # Check if queue mode is enabled (default: True for production)
        use_queue = os.environ.get('CONTAINER_QUEUE_ENABLED', 'true').lower() == 'true'
        
        if use_queue:
            # Queue-based container creation (prevents race conditions)
            container_queue = get_container_queue()
            
            # Callbacks for WebSocket notifications
            def on_success(container):
                """Called when container is successfully created"""
                try:
                    from app.routes.websocket_routes import emit_container_created
                    emit_container_created(container, user.id)
                    current_app.logger.info(f"Container created via queue: {container.container_name}")
                except Exception as e:
                    current_app.logger.error(f"Error in success callback: {e}")
            
            def on_error(error):
                """Called when container creation fails"""
                try:
                    from app.routes.websocket_routes import socketio
                    if socketio:
                        socketio.emit('container_error', {
                            'error': str(error),
                            'desktop_type': desktop_type,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }, room=f"user_{user.id}")
                    current_app.logger.error(f"Container creation failed in queue: {error}")
                except Exception as e:
                    current_app.logger.error(f"Error in error callback: {e}")
            
            # Create and enqueue request
            creation_request = ContainerCreationRequest(
                user_id=user.id,
                session_id=oauth_session.id,
                username=user.username,
                desktop_type=desktop_type,
                desktop_image_id=desktop_type_record.id if desktop_type_record else None,
                callback=on_success,
                error_callback=on_error
            )
            
            request_id = container_queue.enqueue(creation_request)
            queue_size = container_queue.get_queue_size()
            
            return jsonify({
                'success': True,
                'status': 'queued',
                'message': get_message('container_queued', lang) if lang else f'Container creation queued (position: {queue_size})',
                'request_id': request_id,
                'queue_position': queue_size,
                'desktop_type': desktop_type
            }), 202  # HTTP 202 Accepted
        else:
            # Legacy synchronous creation (for backward compatibility)
            docker_manager = DockerManager()
            container = docker_manager.create_container(
                user_id=user.id,
                session_id=oauth_session.id,
                username=user.username,
                desktop_type=desktop_type,
                desktop_image_id=desktop_type_record.id if desktop_type_record else None
            )
            
            url = docker_manager.get_container_url(container)
            
            return jsonify({
                'success': True,
                'message': get_message('container_started', lang),
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
@require_auth
def get_container_status(user_dict):
    """Get status of user's container"""
    lang = get_language_from_request()
    
    try:
        # Get oauth_session from request context (set by require_auth)
        oauth_session = request.oauth_session
        
        # Get container for this session
        container = Container.get_by_session(oauth_session.id)
        
        if not container:
            return jsonify({
                'success': True,
                'has_container': False,
                'message': get_message('no_container', lang)
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
@require_auth
def stop_container(user_dict):
    """Stop user's container"""
    lang = get_language_from_request()
    
    try:
        # Get oauth_session from request context (set by require_auth)
        oauth_session = request.oauth_session
        
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
                'error': get_message('no_running_container', lang)
            }), 404
        
        # Stop the container
        docker_manager = DockerManager()
        docker_manager.stop_container(container)
        
        return jsonify({
            'success': True,
            'message': get_message('container_stopped', lang)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to stop container: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/remove', methods=['POST', 'DELETE'])
@require_auth
def remove_container(user_dict):
    """Remove user's container"""
    lang = get_language_from_request()
    
    try:
        # Get oauth_session from request context (set by require_auth)
        oauth_session = request.oauth_session
        
        # Get container for this session
        container = Container.get_by_session(oauth_session.id)
        
        if not container:
            # Also check for any stopped containers
            container = Container.query.filter_by(session_id=oauth_session.id).first()
        
        if not container:
            return jsonify({
                'success': False,
                'error': get_message('container_not_found', lang)
            }), 404
        
        # Remove the container
        docker_manager = DockerManager()
        docker_manager.remove_container(container)
        
        return jsonify({
            'success': True,
            'message': get_message('container_removed', lang)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to remove container: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_bp.route('/container/list', methods=['GET'])
@require_auth
def list_containers(user_dict):
    """List all containers for the user (only for assigned desktop images)"""
    try:
        # Get oauth_session and user from request context (set by require_auth)
        oauth_session = request.oauth_session
        user = oauth_session.user
        user_group_ids = [g.id for g in user.groups]
        
        # Get all containers for this user
        containers = Container.get_by_user(user.id)
        current_app.logger.info(f"User {user.username} has {len(containers)} total containers")
        
        # Get current status for each
        docker_manager = DockerManager()
        container_list = []
        
        for container in containers:
            current_app.logger.info(f"Checking container {container.container_name}: desktop_type={container.desktop_type}, desktop_image_id={container.desktop_image_id}, status={container.status}")
            
            # Check if user still has access to this desktop image
            if container.desktop_image_id:
                has_access, _ = DesktopAssignment.check_access(container.desktop_image_id, user.id, user_group_ids)
                current_app.logger.info(f"Container {container.container_name}: has_access={has_access}")
                if not has_access:
                    # User no longer has access to this desktop image, skip this container
                    current_app.logger.info(f"Skipping container {container.container_name}: no access")
                    continue
            else:
                # Old container without desktop_image_id (from old structure), skip it
                current_app.logger.info(f"Skipping container {container.container_name}: no desktop_image_id")
                continue
            
            status_info = docker_manager.get_container_status(container)
            current_app.logger.info(f"Container {container.container_name}: status_info={status_info}")
            url = docker_manager.get_container_url(container)
            
            container_info = container.to_dict()
            # Update status from actual Docker state
            container_info['status'] = status_info.get('status', container.status)
            container_info['docker_status'] = status_info.get('docker_status', 'unknown')
            container_info['url'] = url
            container_list.append(container_info)
        
        current_app.logger.info(f"Returning {len(container_list)} containers to user {user.username}")
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
@require_auth
def get_available_desktop_types(user_dict):
    """Get list of desktop types available to the current user"""
    try:
        # Get oauth_session and user from request context (set by require_auth)
        oauth_session = request.oauth_session
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
@require_auth
def check_container_health(user_dict):
    """Check if a specific container is ready and responding"""
    lang = get_language_from_request()
    
    try:
        # Get oauth_session from request context (set by require_auth)
        oauth_session = request.oauth_session
        
        desktop_type = request.args.get('desktop_type')
        
        if not desktop_type:
            return jsonify({
                'success': False,
                'error': get_message('desktop_type_param_required', lang)
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
                'error': get_message('container_not_running', lang)
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



@container_bp.route('/container/queue/stats', methods=['GET'])
@require_auth
def get_queue_stats(user_dict):
    """Get container creation queue statistics"""
    try:
        container_queue = get_container_queue()
        stats = container_queue.get_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get queue stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500