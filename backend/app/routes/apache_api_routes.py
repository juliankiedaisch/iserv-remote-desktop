"""
API endpoint for Apache RewriteMap to query container targets.
"""
from flask import Blueprint, request, jsonify, current_app
from app.models.containers import Container
from sqlalchemy import func
import subprocess
import os

apache_api_bp = Blueprint('apache_api', __name__, url_prefix='/api/apache')

# Shared secret for Apache authentication
APACHE_API_KEY = os.environ.get('APACHE_API_KEY', 'change-this-in-production')

@apache_api_bp.route('/container-target/<proxy_path>', methods=['GET'])
def get_container_target(proxy_path):
    """
    Get container IP:port for Apache proxy routing.
    
    Returns:
        JSON: {"target": "IP:PORT"} or {"target": null}
    """
    # Authenticate Apache server
    api_key = request.headers.get('X-API-Key')
    if api_key != APACHE_API_KEY:
        current_app.logger.warning(f"Error Apache API: No Correct API KEY")
        return jsonify({"error": "Unauthorized"}), 401
    
    # Look up running container by proxy_path (case-insensitive)
    container = Container.query.filter(
        func.lower(Container.proxy_path) == func.lower(proxy_path),
        Container.status == 'running'
    ).first()
    
    if not container or not container.host_port:
        # Log all running containers for debugging
        all_running = Container.query.filter_by(status='running').all()
        current_app.logger.warning(f"Error Apache API: No Target for proxy_path='{proxy_path}'. Running containers: {[(c.container_name, c.proxy_path, c.host_port) for c in all_running]}")
        return jsonify({"target": None})
    
    # Return Docker host IP with mapped port
    # Apache can access the host's mapped ports (7000, 7001, etc.)
    docker_host = os.environ.get('DOCKER_HOST_IP', '172.22.0.36')
    current_app.logger.info(f"Apache API: {docker_host}:{container.host_port}")
    
    return jsonify({"target": f"{docker_host}:{container.host_port}"})
