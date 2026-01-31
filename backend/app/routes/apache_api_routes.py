"""
API endpoint for Apache RewriteMap to query container targets.
"""
from flask import Blueprint, request, jsonify, current_app
from app.models.containers import Container
from sqlalchemy import func
import subprocess
import os

apache_api_bp = Blueprint('apache_api', __name__)

# Shared secret for Apache authentication
APACHE_API_KEY = os.environ.get('APACHE_API_KEY', 'lFSSwVI4bzjY5XJuEWAVXB')

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
