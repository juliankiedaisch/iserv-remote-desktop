from flask import Blueprint, request, Response, current_app
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from app.models.containers import Container
from datetime import datetime, timezone
from app import db
from app.services.docker_manager import DockerManager
import os
import base64
import re

proxy_bp = Blueprint('proxy', __name__)

# Configuration constants
PROXY_CONNECT_TIMEOUT = 10  # seconds to wait for initial connection
PROXY_READ_TIMEOUT = 300  # seconds to wait for response (5 minutes for desktop operations)
DEFAULT_RETRIES = 3  # number of retry attempts for transient failures
DEFAULT_BACKOFF_FACTOR = 0.3  # exponential backoff factor (0.3s, 0.6s, 1.2s)
# Hop-by-hop headers are connection-specific and should not be forwarded in proxy scenarios
# They control the connection between the client and proxy, not between proxy and target server
HOP_BY_HOP_HEADERS = frozenset([
    'host', 'connection', 'keep-alive', 'proxy-authenticate',
    'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade'
])
ALLOWED_HTTP_METHODS = frozenset([
    "HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST", "PATCH"
])
DEFAULT_STATUS_FORCELIST = frozenset([500, 502, 503, 504])
# Asset path prefixes that are commonly used in web applications
# These paths should not be treated as container proxy paths
ASSET_PREFIXES = ('assets', 'js', 'css', 'fonts', 'images', 'static', 'dist', 'build')


def is_asset_path(path):
    """
    Check if a path looks like an asset path (e.g., starts with 'assets/', 'js/', etc.)
    
    Uses exact prefix matching on the first path component to avoid false positives
    like 'assetsfoo' or 'assets-bar' which are not actual asset paths.
    
    Args:
        path: The path to check (e.g., 'assets/ui.js', 'user.name-desktop')
        
    Returns:
        True if the path starts with an asset prefix, False otherwise
    """
    return any(path.split('/')[0] == prefix for prefix in ASSET_PREFIXES)


def create_retry_session(retries=DEFAULT_RETRIES, backoff_factor=DEFAULT_BACKOFF_FACTOR, status_forcelist=DEFAULT_STATUS_FORCELIST, verify_ssl=True):
    """
    Create a requests session with retry logic
    
    Args:
        retries: Number of retries to attempt
        backoff_factor: Factor for exponential backoff (0.3 means 0.3s, 0.6s, 1.2s delays)
        status_forcelist: HTTP status codes to retry on
        verify_ssl: Whether to verify SSL certificates (default: True)
        
    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    session.verify = verify_ssl
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=ALLOWED_HTTP_METHODS
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@proxy_bp.route('/desktop/<path:proxy_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@proxy_bp.route('/desktop/<path:proxy_path>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_to_container(proxy_path, subpath=''):
    """
    Reverse proxy route that forwards all requests to the appropriate container
    
    This handles the proxy routing from /desktop/username-desktoptype to the actual container port
    """
    try:
        # Check if this is an asset request (common asset paths)
        # Asset paths like 'assets', 'js', 'css', 'fonts', 'images', 'static' are not container names
        is_potential_asset = is_asset_path(proxy_path)
        
        # Find the container by proxy path
        container = Container.get_by_proxy_path(proxy_path)
        
        # If no container found and this looks like an asset path, try to find container from Referer
        if not container and is_potential_asset:
            referer = request.headers.get('Referer', '')
            current_app.logger.debug(f"Asset request detected for {proxy_path}, checking Referer: {referer}")
            
            if referer:
                # Extract the container proxy_path from the Referer URL
                # Referer format: https://domain/desktop/username-desktoptype or similar
                match = re.search(r'/desktop/([^/?#]+)', referer)
                if match:
                    referer_proxy_path = match.group(1)
                    # Check if this referer path is NOT an asset path itself
                    if not is_asset_path(referer_proxy_path):
                        container = Container.get_by_proxy_path(referer_proxy_path)
                        if container:
                            current_app.logger.debug(f"Found container from Referer: {referer_proxy_path}")
                            # Reconstruct the full asset path by combining proxy_path and subpath
                            # The original proxy_path (e.g., 'assets') is actually part of the URL path to the container
                            # Example: /desktop/assets/ui.js -> container from referer, path: assets/ui.js
                            if subpath:
                                subpath = f"{proxy_path}/{subpath}"
                            else:
                                subpath = proxy_path
        
        if not container:
            current_app.logger.warning(f"No running container found for proxy path: {proxy_path}")
            return Response("Container not found or not running", status=404)
        
        if not container.host_port:
            current_app.logger.error(f"Container {container.container_name} has no host port assigned")
            return Response("Container port not available", status=500)
        
        # Update last accessed time
        container.last_accessed = datetime.now(timezone.utc)
        db.session.commit()
        
        # Determine protocol based on environment variable (default to HTTPS for Kasm containers)
        container_protocol = os.environ.get('KASM_CONTAINER_PROTOCOL', 'https')
        
        # Build the target URL for the container
        target_url = f"{container_protocol}://localhost:{container.host_port}"
        if subpath:
            target_url = f"{target_url}/{subpath}"
        
        # Forward query parameters
        if request.query_string:
            target_url = f"{target_url}?{request.query_string.decode('utf-8')}"
        
        current_app.logger.debug(f"Proxying request to: {target_url}")
        
        # Prepare headers (remove hop-by-hop headers)
        headers = {}
        for key, value in request.headers:
            if key.lower() not in HOP_BY_HOP_HEADERS:
                headers[key] = value
        
        # Add HTTP Basic Auth for VNC password to avoid manual authentication
        # This allows users to access containers without entering credentials
        vnc_user = os.environ.get('VNC_USER', 'kasm_user')
        vnc_password = os.environ.get('VNC_PASSWORD', 'password')
        credentials = f"{vnc_user}:{vnc_password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers['Authorization'] = f"Basic {encoded_credentials}"
        
        # Forward the request to the container with retry logic
        try:
            # Create session with retry logic for transient failures
            # Disable SSL verification for localhost connections with self-signed certificates
            verify_ssl = os.environ.get('KASM_VERIFY_SSL', 'false').lower() == 'true'
            session = create_retry_session(verify_ssl=verify_ssl)
            
            # Suppress SSL warnings when verification is disabled
            if not verify_ssl:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Use longer timeout for desktop environments
            # Desktop operations can involve large file transfers and rendering
            resp = session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                stream=True,
                timeout=(PROXY_CONNECT_TIMEOUT, PROXY_READ_TIMEOUT)
            )
            
            # Create response with the same status code
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            response_headers = [
                (name, value) for (name, value) in resp.raw.headers.items()
                if name.lower() not in excluded_headers
            ]
            
            # Stream the response back with larger chunks for better performance
            # 64KB chunks are optimal for high-bandwidth desktop streaming
            response = Response(
                resp.iter_content(chunk_size=64*1024),
                status=resp.status_code,
                headers=response_headers
            )
            
            return response
            
        except requests.exceptions.ConnectionError as e:
            current_app.logger.error(f"Connection error proxying to container: {str(e)}")
            # Check if container is still running before returning error
            try:
                manager = DockerManager()
                status = manager.get_container_status(container)
                if status.get('status') != 'running':
                    return Response(
                        "Container is not running. Please wait a moment and refresh, or restart the container.",
                        status=503
                    )
            except Exception as status_check_error:
                current_app.logger.warning(f"Failed to check container status: {str(status_check_error)}")
            
            return Response(
                "Unable to connect to container. The container may still be starting up. "
                "Please wait a moment and refresh the page.",
                status=503
            )
        except requests.exceptions.Timeout as e:
            current_app.logger.error(f"Timeout proxying request to container: {str(e)}")
            return Response(
                "Connection to container timed out. The container may be overloaded or not responding.",
                status=504
            )
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
