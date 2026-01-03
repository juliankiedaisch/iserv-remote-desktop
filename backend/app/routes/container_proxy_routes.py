"""
Container proxy routes - Handle dynamic proxying to VNC containers.
This is used by the nginx reverse proxy to route subdomain requests to containers.
"""
from flask import Blueprint, request, Response, redirect
import requests
import os
import base64
from app.models.containers import Container

container_proxy_bp = Blueprint('container_proxy', __name__)

# Docker host IP for accessing published container ports
# When running in Docker, use host.docker.internal to access host ports
DOCKER_HOST_IP = os.environ.get('DOCKER_HOST_IP', 'host.docker.internal')

# KasmVNC credentials - these match the VNC_USER and VNC_PASSWORD used when creating containers
# Format: base64(VNC_USER:VNC_PASSWORD)
VNC_USER = os.environ.get('VNC_USER', 'kasm_user')
VNC_PASSWORD = os.environ.get('VNC_PASSWORD', 'password')
VNC_AUTH_HEADER = 'Basic ' + base64.b64encode(f'{VNC_USER}:{VNC_PASSWORD}'.encode()).decode()

@container_proxy_bp.route('/container-proxy/<proxy_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
@container_proxy_bp.route('/container-proxy/<proxy_path>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
def proxy_to_container(proxy_path, subpath=''):
    """
    Dynamically proxy requests to VNC containers based on proxy_path.
    
    This endpoint receives requests from nginx for desktop-*.hub.mdg-hamburg.de subdomains
    and forwards them to the appropriate container using published host ports.
    
    Args:
        proxy_path: The proxy path extracted from subdomain (e.g., "user-ubuntu-desktop")
        subpath: Optional path component after the proxy_path
    
    Returns:
        Proxied response from the container or redirect if not found
    """
    # Look up running container by proxy_path
    container = Container.query.filter_by(
        proxy_path=proxy_path,
        status='running'
    ).first()
    
    # If container not found or no host port, redirect to main domain
    if not container or not container.host_port:
        return redirect('https://desktop.hub.mdg-hamburg.de/', code=302)
    
    # Build target URL using Docker host IP and published port
    # Containers are accessible via their published host ports
    target_url = f"https://{DOCKER_HOST_IP}:{container.host_port}/{subpath}"
    
    # Get query string from original request
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"
    
    # Prepare headers for proxying
    headers = {}
    for key, value in request.headers:
        # Skip host header as we're changing the target
        if key.lower() not in ['host', 'content-length', 'transfer-encoding']:
            headers[key] = value
    
    # Add KasmVNC Basic Auth credentials for seamless access
    # This matches the credentials configured in containers
    headers['Authorization'] = VNC_AUTH_HEADER
    
    try:
        # Forward the request to the container
        # NOTE: SSL verification is disabled because Kasm containers use self-signed certificates
        # This is acceptable in this context because:
        # 1. Containers are accessed via localhost/host.docker.internal (trusted network)
        # 2. Containers are managed by this application (not external services)
        # 3. Authentication is handled via Basic Auth credentials
        # For production with multiple hosts, consider using a custom CA or certificate pinning
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            allow_redirects=False,
            verify=False,  # Containers use self-signed certificates (see note above)
            stream=True,   # Stream response for large files and WebSocket upgrade
            timeout=3600   # Long timeout for desktop sessions
        )
        
        # Stream the response back to the client
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        # Build response headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [
            (name, value) for (name, value) in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]
        
        # Return streaming response
        return Response(
            generate(),
            status=resp.status_code,
            headers=response_headers
        )
        
    except requests.exceptions.RequestException as e:
        # If connection fails, log and redirect to main domain
        import logging
        logging.error(f"Failed to proxy to container {proxy_path}: {str(e)}")
        return redirect('https://desktop.hub.mdg-hamburg.de/', code=302)
