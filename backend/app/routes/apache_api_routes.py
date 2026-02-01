"""
API endpoint for Apache RewriteMap to query container targets.
"""
from flask import Blueprint, request, jsonify, current_app
from app.models.containers import Container
from app.models.oauth_session import OAuthSession
from app.models.users import User
from sqlalchemy import func
from datetime import datetime, timezone
import subprocess
import os

apache_api_bp = Blueprint('apache_api', __name__)

# Shared secret for Apache authentication
APACHE_API_KEY = os.environ.get('APACHE_API_KEY', 'lFSSwVI4bzjY5XJuEWAVXB')

@apache_api_bp.route('/container-access-check', methods=['GET'])
def check_container_access():
    """
    Check if a user has access to a container via subdomain.
    
    This endpoint is called by nginx auth_request to verify access permissions.
    It extracts the subdomain from the X-Original-URI header and checks if the
    authenticated user has permission to access the container.
    
    Headers:
        Cookie: Session cookie for authentication
        X-Original-URI: Original request URI (e.g., https://test-desktop-user-xxx.hub.mdg-hamburg.de/)
        X-Real-IP: Client IP address
        
    Returns:
        200: User has access to the container
        401: User is not authenticated
        403: User does not have access to the container
        404: Container not found
    """
    from app import db
    
    # Extract session from cookies
    session_id = None
    cookies = request.headers.get('Cookie', '')
    
    # Parse cookies to extract session_id
    # Format: "session_id=value; other_cookie=value"
    for cookie in cookies.split(';'):
        cookie = cookie.strip()
        if cookie.startswith('session_id='):
            session_id = cookie.split('=', 1)[1]
            break
    
    if not session_id:
        current_app.logger.warning("Container access check: No session_id in cookies")
        return jsonify({"error": "Authentication required"}), 401
    
    # Validate session
    oauth_session = OAuthSession.get_by_session_id(session_id)
    if not oauth_session:
        current_app.logger.warning(f"Container access check: Invalid session {session_id}")
        return jsonify({"error": "Invalid session"}), 401
    
    # Check if session is expired
    expires_at = oauth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        current_app.logger.warning(f"Container access check: Expired session for user {oauth_session.user.username}")
        return jsonify({"error": "Session expired"}), 401
    
    user = oauth_session.user
    
    # Extract subdomain from X-Original-URI
    original_uri = request.headers.get('X-Original-URI', '')
    host = request.headers.get('Host', '')
    
    current_app.logger.info(f"Container access check: user={user.username}, host={host}, uri={original_uri}")
    
    # Extract proxy_path from subdomain
    # Format: test-desktop-{proxy_path}.hub.mdg-hamburg.de or test-audio-{proxy_path}.hub.mdg-hamburg.de
    prefix = os.environ.get('CONTAINER_PREFIX', 'test-desktop')
    prefix = prefix.rstrip('-')
    
    proxy_path = None
    if host.startswith(f"{prefix}-"):
        # Remove prefix and domain
        # e.g., "test-desktop-user-ubuntu-token123.hub.mdg-hamburg.de" -> "user-ubuntu-token123"
        remaining = host[len(f"{prefix}-"):]
        proxy_path = remaining.split('.')[0]  # Remove domain part
    elif host.startswith("test-audio-"):
        # Handle audio subdomain
        remaining = host[len("test-audio-"):]
        proxy_path = remaining.split('.')[0]
    
    if not proxy_path:
        current_app.logger.warning(f"Container access check: Could not extract proxy_path from host {host}")
        return jsonify({"error": "Invalid container URL"}), 404
    
    current_app.logger.info(f"Container access check: Extracted proxy_path={proxy_path}")
    
    # Look up container by proxy_path
    container = Container.query.filter(
        func.lower(Container.proxy_path) == func.lower(proxy_path),
        Container.status == 'running'
    ).first()
    
    if not container:
        current_app.logger.warning(f"Container access check: Container not found for proxy_path={proxy_path}")
        return jsonify({"error": "Container not found"}), 404
    
    # Check access permissions
    # 1. Owner has access
    if container.user_id == user.id:
        current_app.logger.info(f"Container access check: User {user.username} is owner of container {container.container_name}")
        return '', 200
    
    # 2. Teachers and admins have access to all containers
    if user.is_admin or user.is_teacher:
        current_app.logger.info(f"Container access check: User {user.username} has {user.role} role, granting access to container {container.container_name}")
        return '', 200
    
    # 3. No access
    current_app.logger.warning(f"Container access check: User {user.username} (role={user.role}) denied access to container {container.container_name} owned by {container.user_id}")
    return jsonify({"error": "Access denied"}), 403

@apache_api_bp.route('/container-target/<proxy_path>', methods=['GET'])
def get_container_target(proxy_path):
    """
    Get container IP:port for Apache proxy routing.
    Supports both VNC and audio port routing.
    
    Query params:
        port_type: 'vnc' or 'audio' (default: 'vnc')
    
    Returns:
        JSON: {"target": "IP:PORT"} or {"target": null}
    """
    # Authenticate Apache server
    api_key = request.headers.get('X-API-Key')
    current_app.logger.info(f"Apache API auth check: received='{api_key}', expected='{APACHE_API_KEY}', match={api_key == APACHE_API_KEY}")
    if api_key != APACHE_API_KEY:
        current_app.logger.warning(f"Error Apache API: No Correct API KEY")
        return jsonify({"error": "Unauthorized"}), 401
    
    # Get port type (vnc or audio)
    port_type = request.args.get('port_type', 'vnc')
    
    current_app.logger.info(f"Apache API: Looking for proxy_path='{proxy_path}' (lowercase: '{proxy_path.lower()}'), port_type='{port_type}'")
    
    # Look up running container by proxy_path (case-insensitive)
    container = Container.query.filter(
        func.lower(Container.proxy_path) == func.lower(proxy_path),
        Container.status == 'running'
    ).first()
    
    if not container or not container.host_port:
        # Log all running containers for debugging with detailed info
        all_running = Container.query.filter_by(status='running').all()
        current_app.logger.warning(
            f"Error Apache API: No Target for proxy_path='{proxy_path}' (lowercase: '{proxy_path.lower()}') port_type='{port_type}'. "
            f"Running containers: {[(c.container_name, c.proxy_path, c.proxy_path.lower() if c.proxy_path else None, c.host_port) for c in all_running]}"
        )
        return jsonify({"target": None})
    
    # Return Docker host IP with mapped port
    docker_host = os.environ.get('DOCKER_HOST_IP', '172.22.0.36')
    
    if port_type == 'audio':
        # Get audio port from database, fallback to Docker labels for old containers
        audio_port = container.audio_port
        
        if not audio_port and container.container_id:
            # Try to get from Docker labels (for containers created before audio_port column was added)
            try:
                from app.services.docker_manager import DockerManager
                docker_manager = DockerManager()
                docker_container = docker_manager.client.containers.get(container.container_id)
                audio_port_str = docker_container.labels.get('audio_port')
                if audio_port_str:
                    audio_port = int(audio_port_str)
                    # Update database for future requests
                    container.audio_port = audio_port
                    from app import db
                    db.session.commit()
                    current_app.logger.info(f"Populated audio_port from Docker labels for {container.container_name}: {audio_port}")
            except Exception as e:
                current_app.logger.error(f"Failed to get audio port from Docker labels: {e}")
        
        if audio_port:
            current_app.logger.info(f"Apache API (audio): {docker_host}:{audio_port}")
            return jsonify({"target": f"{docker_host}:{audio_port}"})
        else:
            current_app.logger.error(f"No audio port configured for container {container.container_name}")
            return jsonify({"target": None})
    
    # Default: return VNC port
    current_app.logger.info(f"Apache API (vnc): {docker_host}:{container.host_port}")
    return jsonify({"target": f"{docker_host}:{container.host_port}"})
