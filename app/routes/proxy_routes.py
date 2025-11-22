from flask import Blueprint, request, Response, current_app
import requests
from app.models.containers import Container
from datetime import datetime, timezone
from app import db

proxy_bp = Blueprint('proxy', __name__)


@proxy_bp.route('/desktop/<path:proxy_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@proxy_bp.route('/desktop/<path:proxy_path>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_to_container(proxy_path, subpath=''):
    """
    Reverse proxy route that forwards all requests to the appropriate container
    
    This handles the proxy routing from /desktop/username-desktoptype to the actual container port
    """
    try:
        # Find the container by proxy path
        container = Container.get_by_proxy_path(proxy_path)
        
        if not container:
            current_app.logger.warning(f"No running container found for proxy path: {proxy_path}")
            return Response("Container not found or not running", status=404)
        
        if not container.host_port:
            current_app.logger.error(f"Container {container.container_name} has no host port assigned")
            return Response("Container port not available", status=500)
        
        # Update last accessed time
        container.last_accessed = datetime.now(timezone.utc)
        db.session.commit()
        
        # Build the target URL for the container
        target_url = f"http://localhost:{container.host_port}"
        if subpath:
            target_url = f"{target_url}/{subpath}"
        
        # Forward query parameters
        if request.query_string:
            target_url = f"{target_url}?{request.query_string.decode('utf-8')}"
        
        current_app.logger.debug(f"Proxying request to: {target_url}")
        
        # Prepare headers (remove hop-by-hop headers)
        headers = {}
        for key, value in request.headers:
            if key.lower() not in ['host', 'connection', 'keep-alive', 'proxy-authenticate', 
                                   'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade']:
                headers[key] = value
        
        # Forward the request to the container
        try:
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                stream=True,
                timeout=30
            )
            
            # Create response with the same status code
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            response_headers = [
                (name, value) for (name, value) in resp.raw.headers.items()
                if name.lower() not in excluded_headers
            ]
            
            # Stream the response back
            response = Response(
                resp.iter_content(chunk_size=10*1024),
                status=resp.status_code,
                headers=response_headers
            )
            
            return response
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error proxying request to container: {str(e)}")
            return Response(f"Error connecting to container: {str(e)}", status=502)
    
    except Exception as e:
        current_app.logger.error(f"Proxy error: {str(e)}")
        return Response(f"Internal proxy error: {str(e)}", status=500)


@proxy_bp.route('/desktop/<path:proxy_path>/websockify', methods=['GET'])
def proxy_websocket(proxy_path):
    """
    Special handler for WebSocket connections (used by Kasm/noVNC)
    
    Note: This is a simplified version. For production, use a proper 
    WebSocket proxy like nginx or a Flask-SocketIO implementation.
    """
    container = Container.get_by_proxy_path(proxy_path)
    
    if not container:
        current_app.logger.warning(f"No running container found for websocket proxy path: {proxy_path}")
        return Response("Container not found or not running", status=404)
    
    # For WebSocket connections, we need a proper WebSocket proxy
    # This is a placeholder that redirects to the direct WebSocket endpoint
    # In production, use nginx or another proper WebSocket proxy
    current_app.logger.warning(
        f"WebSocket proxy requested for {proxy_path}. "
        f"Consider using nginx for WebSocket proxying in production."
    )
    
    # Return information about where the WebSocket should connect
    # This is handled by nginx or the client needs to connect differently
    return Response(
        f"WebSocket endpoint: ws://localhost:{container.host_port}/websockify",
        status=200,
        mimetype='text/plain'
    )
