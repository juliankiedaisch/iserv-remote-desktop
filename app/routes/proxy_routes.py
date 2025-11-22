from flask import Blueprint, request, Response, current_app
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import ProtocolError
from http.client import RemoteDisconnected
from app.models.containers import Container
from datetime import datetime, timezone
from app import db
from app.services.docker_manager import DockerManager
import time

proxy_bp = Blueprint('proxy', __name__)

# Configuration constants
PROXY_CONNECT_TIMEOUT = 10  # seconds to wait for initial connection
PROXY_READ_TIMEOUT = 300  # seconds to wait for response (5 minutes for desktop operations)
DEFAULT_RETRIES = 3  # number of retry attempts for transient failures
DEFAULT_BACKOFF_FACTOR = 0.3  # exponential backoff factor (0.3s, 0.6s, 1.2s)
# Retry settings for container startup scenarios
CONTAINER_STARTUP_RETRIES = 5  # total attempts (1 initial + 4 retries)
CONTAINER_STARTUP_BACKOFF = 2.0  # initial backoff in seconds (delays: 2s, 4s, 8s, 16s for attempts 2-5)
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


def create_retry_session(retries=DEFAULT_RETRIES, backoff_factor=DEFAULT_BACKOFF_FACTOR, status_forcelist=DEFAULT_STATUS_FORCELIST):
    """
    Create a requests session with retry logic
    
    Args:
        retries: Number of retries to attempt
        backoff_factor: Factor for exponential backoff (0.3 means 0.3s, 0.6s, 1.2s delays)
        status_forcelist: HTTP status codes to retry on
        
    Returns:
        Configured requests.Session
    """
    session = requests.Session()
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


def is_container_startup_error(exception):
    """
    Check if an exception indicates the container is still starting up
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if this is a container startup error that should be retried
    """
    # Check for RemoteDisconnected errors (connection closed before response)
    if isinstance(exception, requests.exceptions.ConnectionError):
        # Check the underlying cause via __cause__ attribute
        cause = exception.__cause__
        if cause and isinstance(cause, ProtocolError):
            return True
        
        # Also check __context__ for wrapped exceptions
        context = exception.__context__
        if context and isinstance(context, ProtocolError):
            return True
            
        # Check the string representation for RemoteDisconnected as fallback
        error_str = str(exception)
        if 'RemoteDisconnected' in error_str or 'Remote end closed connection' in error_str:
            return True
    return False


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
            if key.lower() not in HOP_BY_HOP_HEADERS:
                headers[key] = value
        
        # Forward the request to the container with retry logic
        # Manual retry loop for container startup scenarios (RemoteDisconnected errors)
        last_exception = None
        for attempt in range(CONTAINER_STARTUP_RETRIES):
            try:
                # Create session with retry logic for transient failures
                session = create_retry_session()
                
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
                
                # Success! Return the response
                if attempt > 0:
                    current_app.logger.info(f"Successfully connected to container after {attempt + 1} attempts")
                return response
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                
                # Check if this is a container startup error (RemoteDisconnected)
                if is_container_startup_error(e) and attempt < CONTAINER_STARTUP_RETRIES - 1:
                    # Calculate backoff delay with exponential increase
                    delay = CONTAINER_STARTUP_BACKOFF * (2 ** attempt)
                    current_app.logger.warning(
                        f"Container startup error on attempt {attempt + 1}/{CONTAINER_STARTUP_RETRIES}: {str(e)}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
                
                # Not a startup error or last attempt - fall through to error handling
                current_app.logger.error(f"Connection error proxying to container: {str(e)}")
                break
                
            except requests.exceptions.Timeout as e:
                current_app.logger.error(f"Timeout proxying request to container: {str(e)}")
                return Response(
                    "Connection to container timed out. The container may be overloaded or not responding.",
                    status=504
                )
            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"Error proxying request to container: {str(e)}")
                return Response(f"Error connecting to container: {str(e)}", status=502)
        
        # If we get here, all retries failed - handle the last exception
        if last_exception:
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
