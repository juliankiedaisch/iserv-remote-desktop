"""
API endpoint for Apache RewriteMap to query container targets.
"""
from flask import Blueprint, request, jsonify
from app.models.containers import Container
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
        return jsonify({"error": "Unauthorized"}), 401
    
    # Look up running container by proxy_path
    container = Container.query.filter_by(
        proxy_path=proxy_path,
        status='running'
    ).first()
    
    if not container or not container.host_port:
        return jsonify({"target": None})
    
    # Return Docker host IP with mapped port
    # Apache can access the host's mapped ports (7000, 7001, etc.)
    docker_host = os.environ.get('DOCKER_HOST_IP', '172.22.0.27')
    
    return jsonify({"target": f"{docker_host}:{container.host_port}"})
