from flask import Blueprint, request, Response, current_app, session
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from app.models.containers import Container
from datetime import datetime, timezone
from app import db, sock
from app.services.docker_manager import DockerManager
import os
import base64
import re
import socket
import ssl
import traceback

proxy_bp = Blueprint('proxy', __name__)

# Configuration constants
PROXY_CONNECT_TIMEOUT = 10  # seconds to wait for initial connection
PROXY_READ_TIMEOUT = 300  # seconds to wait for response (5 minutes for desktop operations)
WEBSOCKET_PROXY_TIMEOUT = 3600  # seconds to wait for WebSocket proxy to complete (1 hour for desktop sessions)
GREENLET_CLEANUP_WAIT = 0.1  # seconds to wait for greenlet cleanup after kill (100ms)
DEFAULT_RETRIES = 3  # number of retry attempts for transient failures
DEFAULT_BACKOFF_FACTOR = 0.3  # exponential backoff factor (0.3s, 0.6s, 1.2s)
PROXY_CHUNK_SIZE = 64 * 1024  # 64KB chunks for streaming responses (optimal for desktop streaming)
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
# Note: 'app' IS included because Kasm uses /desktop/app/ for application files (like locale files)
ASSET_PREFIXES = ('assets', 'js', 'css', 'fonts', 'images', 'static', 'dist', 'build', 'locale', 'app')

# File extensions that indicate asset/configuration files (not container names)
ASSET_EXTENSIONS = ('.json', '.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.woff', '.woff2', '.ttf', '.eot', '.ico', '.oga', '.mp3', '.wav')


def is_asset_path(path):
    """
    Check if a path looks like an asset path or file request
    
    This checks both:
    1. Path prefixes (e.g., 'assets/', 'js/', 'css/')
    2. File extensions (e.g., '.json', '.css', '.js')
    
    This helps distinguish between container proxy paths (e.g., 'user.name-desktop')
    and actual file/asset requests (e.g., 'package.json', 'assets/ui.js')
    
    Args:
        path: The path to check (e.g., 'assets/ui.js', 'package.json', 'user.name-desktop')
        
    Returns:
        True if the path starts with an asset prefix or has an asset file extension
    """
    first_component = path.split('/')[0]
    
    # Check if it starts with a known asset prefix
    if any(first_component == prefix for prefix in ASSET_PREFIXES):
        return True
    
    # Check if the first component (or full path) has a file extension
    # This catches cases like 'package.json' or 'config.js'
    if any(first_component.endswith(ext) for ext in ASSET_EXTENSIONS):
        return True
    
    return False


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
            
            # If still no container found from Referer, try to get from session
            # This handles nested asset references where the Referer itself is an asset
            if not container:
                session_container_name = session.get('current_container')
                if session_container_name:
                    current_app.logger.debug(f"Trying container from session: {session_container_name}")
                    container = Container.get_by_proxy_path(session_container_name)
                    if container:
                        current_app.logger.debug(f"Found container from session: {session_container_name}")
                        # Reconstruct the full asset path
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
        
        # Store container in session for future asset requests
        # Only update session for non-asset requests (actual desktop page access)
        if not is_potential_asset:
            session['current_container'] = container.proxy_path
            current_app.logger.debug(f"Stored container in session: {container.proxy_path}")
        
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
        
        # Warn if using default password (security risk in production)
        if vnc_password == 'password':
            current_app.logger.warning("Using default VNC password - set VNC_PASSWORD environment variable for production")
        
        credentials = f"{vnc_user}:{vnc_password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers['Authorization'] = f"Basic {encoded_credentials}"
        
        # Forward the request to the container with retry logic
        try:
            # Create session with retry logic for transient failures
            # Disable SSL verification for localhost connections with self-signed certificates
            verify_ssl = os.environ.get('KASM_VERIFY_SSL', 'false').lower() == 'true'
            requests_session = create_retry_session(verify_ssl=verify_ssl)
            
            # Suppress SSL warnings when verification is disabled
            if not verify_ssl:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Use longer timeout for desktop environments
            # Desktop operations can involve large file transfers and rendering
            resp = requests_session.request(
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
            response = Response(
                resp.iter_content(chunk_size=PROXY_CHUNK_SIZE),
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


@proxy_bp.route('/websockify', methods=['GET'])
def proxy_websocket_root():
    """
    Handle WebSocket connections at /websockify (without /desktop/ prefix)
    
    This occurs when Kasm containers make WebSocket requests from their UI.
    We need to determine which container this request is for by checking the Referer header,
    or falling back to the session if Referer is unavailable or points to an asset.
    
    Physical Architecture:
    =====================
    SERVER 1 (Apache):           SERVER 2 (Docker Host):
    - Browser → Apache           - Container 1: user1-vscode (port 7001)
    - Let's Encrypt cert         - Container 2: user1-chromium (port 7002)
    - Apache → Flask (ws://)     - Container 3: user2-vscode (port 7005)
                                 - Container N: userN-desktop (port 700X)
    Flask bridges between servers via network connection
    
    SSL Certificate Chain:
    =====================
    - Public: Browser → Apache (Let's Encrypt wildcard - TRUSTED)
    - Internal: Apache → Flask (unencrypted localhost ws://)
    - Container: Flask → Docker Host (self-signed cert - UNTRUSTED, verify disabled)
    
    Why Flask Cannot Be Bypassed:
    =============================
    1. Physical separation: Apache and containers on different servers
    2. Multi-user routing: Multiple containers, multiple users, simultaneous access
    3. Dynamic port lookup: Container ports determined from database query
    4. SSL verification handling: Must disable cert verification for self-signed certs
    5. Session/authentication: Must verify user has access to requested container
    
    When running with gunicorn + GeventWebSocketWorker or gevent-websocket development server,
    WebSocket connections are available via request.environ.get('wsgi.websocket'). 
    This function handles both regular HTTP requests and WebSocket upgrade requests.
    """
    import sys
    print("=" * 80, flush=True)
    print("[ROUTE ENTRY] /websockify route handler was called!", flush=True)
    print(f"Upgrade header: {request.headers.get('Upgrade')}", flush=True)
    print(f"wsgi.websocket exists: {request.environ.get('wsgi.websocket') is not None}", flush=True)
    print(f"Host header: {request.headers.get('Host')}", flush=True)
    print("=" * 80, flush=True)
    sys.stdout.flush()
    
    referer = request.headers.get('Referer', '')
    host = request.headers.get('Host', '')
    current_app.logger.info(f"WebSocket request at /websockify with Host: {host}, Referer: {referer}")
    # Log minimal information for debugging without exposing sensitive session data
    current_app.logger.debug(f"Session has current_container: {bool(session.get('current_container'))}")
    
    # Check if this is a WebSocket upgrade request
    ws = request.environ.get('wsgi.websocket')
    is_websocket = ws is not None or (
        request.headers.get('Upgrade', '').lower() == 'websocket' and
        'upgrade' in request.headers.get('Connection', '').lower()
    )
    
    if is_websocket:
        current_app.logger.info("WebSocket upgrade request detected")
        if ws:
            current_app.logger.info("wsgi.websocket object is available")
        else:
            current_app.logger.warning("wsgi.websocket object is NOT available (may be handled by Apache)")
    else:
        current_app.logger.info("NOT a WebSocket upgrade request")
    
    container = None
    
    # PRIORITY 1: Try to extract container from subdomain
    # Format: container-name.desktop.hub.mdg-hamburg.de
    if host and '.desktop.hub.mdg-hamburg.de' in host:
        subdomain = host.split('.desktop.hub.mdg-hamburg.de')[0]
        current_app.logger.error(f"DEBUG: Host={host}, Extracted subdomain={subdomain}")
        if subdomain and subdomain != 'desktop':
            current_app.logger.error(f"DEBUG: Looking for container with proxy_path={subdomain}")
            # Find container by proxy_path (subdomain should match proxy_path)
            container = Container.get_by_proxy_path(subdomain)
            if container:
                current_app.logger.error(f"DEBUG: ✓ Found container from subdomain: {subdomain} -> {container.container_name}")
            else:
                current_app.logger.error(f"DEBUG: ✗ Container not found for subdomain: {subdomain}")
                # Debug: List all containers
                all_containers = Container.query.all()
                current_app.logger.error(f"DEBUG: Available containers: {[(c.container_name, c.proxy_path) for c in all_containers]}")
    
    # PRIORITY 2: Try to find container from Referer (backward compatibility)
    if referer:
        # Validate Referer length to prevent ReDoS attacks
        if len(referer) > 2048:  # Max reasonable URL length
            current_app.logger.warning(f"Referer header too long: {len(referer)} bytes")
            return Response("Invalid Referer header", status=400)
        
        # Extract the container proxy_path from the Referer URL
        # Referer format: https://domain/desktop/username-desktoptype or similar
        # Use a simple, non-backtracking pattern to prevent ReDoS
        match = re.search(r'/desktop/([^/?#]+)', referer)
        if match:
            referer_proxy_path = match.group(1)
            current_app.logger.info(f"Extracted proxy_path from Referer: {referer_proxy_path}")
            
            # Validate extracted path length
            if len(referer_proxy_path) > 255:  # Max reasonable proxy path length
                current_app.logger.warning(f"Extracted proxy path too long: {len(referer_proxy_path)} chars")
                return Response("Invalid container path", status=400)
            
            # Check if this referer path is NOT an asset path
            if not is_asset_path(referer_proxy_path):
                # Find the container
                container = Container.get_by_proxy_path(referer_proxy_path)
                if container:
                    current_app.logger.info(f"Found container from Referer: {referer_proxy_path} -> {container.container_name}")
                else:
                    current_app.logger.warning(f"Container not found for proxy_path from Referer: {referer_proxy_path}")
            else:
                current_app.logger.debug(f"Referer path is an asset: {referer_proxy_path}, trying session")
        else:
            current_app.logger.warning(f"Could not extract proxy_path from Referer: {referer}")
    else:
        current_app.logger.warning("No Referer header in WebSocket request")
    
    # If no container found from Referer, try session
    if not container:
        session_container_name = session.get('current_container')
        current_app.logger.info(f"Trying to find container from session: {session_container_name}")
        if session_container_name:
            current_app.logger.debug(f"Trying container from session for WebSocket: {session_container_name}")
            container = Container.get_by_proxy_path(session_container_name)
            if container:
                current_app.logger.info(f"Found container from session for WebSocket: {session_container_name} -> {container.container_name}")
            else:
                current_app.logger.warning(f"Container not found for proxy_path from session: {session_container_name}")
        else:
            current_app.logger.warning("No current_container in session")
    
    if not container:
        session_container = session.get('current_container')
        error_msg = f"No running container found for websocket (Referer: {referer}, Session container: {'present' if session_container else 'missing'})"
        current_app.logger.warning(error_msg)
        
        # For WebSocket requests, return a proper error response
        # Use code 1011 (server error) when container is not found
        # Code 1002 would be for protocol errors, which this is not
        if is_websocket:
            # If we have a ws object, close it properly with an error code
            if ws:
                try:
                    ws.close(1011, "Container not found")
                except Exception as e:
                    current_app.logger.error(f"Error closing WebSocket: {e}")
                return None
            else:
                # No ws object, return HTTP error
                return Response(
                    "Container not found or not running. Please access the desktop page first to establish a session.",
                    status=404,
                    mimetype='text/plain'
                )
        else:
            return Response("Container not found or not running. Please access the desktop page first.", status=404)
    
    if not container.host_port:
        current_app.logger.error(f"Container {container.container_name} has no host port assigned")
        return Response("Container port not available", status=500)
    
    # Update last accessed time
    container.last_accessed = datetime.now(timezone.utc)
    db.session.commit()
    
    # Determine protocol based on environment variable
    container_protocol = os.environ.get('KASM_CONTAINER_PROTOCOL', 'https')
    use_ssl = container_protocol == 'https'
    
    current_app.logger.info(f"Proxying WebSocket to container {container.container_name} on port {container.host_port}")
    
    # If this is a WebSocket upgrade request and we have a WebSocket object from gevent-websocket
    if ws:
        current_app.logger.info("Handling WebSocket with gevent-websocket")
        return _proxy_websocket_with_gevent(ws, container, use_ssl)
    elif is_websocket:
        # WebSocket upgrade request but no ws object (e.g., running with Werkzeug dev server)
        # Return a proper WebSocket handshake response that Apache/Nginx can intercept
        current_app.logger.info("Returning WebSocket handshake for Apache/Nginx to handle")
        return _return_websocket_handshake(container, use_ssl)
    else:
        # Regular HTTP request (for testing/debugging)
        current_app.logger.debug("Regular HTTP request to /websockify (not WebSocket)")
        return Response(
            f"This endpoint is for WebSocket connections only. "
            f"Container: {container.container_name}, Port: {container.host_port}",
            status=200,
            mimetype='text/plain'
        )


def _proxy_websocket_with_gevent(ws, container, use_ssl):
    """
    Proxy WebSocket connection between client and container using gevent
    
    This implementation uses gevent-websocket which provides the WebSocket handler
    when running with gunicorn + GeventWebSocketWorker or the gevent-websocket 
    development server (pywsgi.WSGIServer with WebSocketHandler).
    
    Why Manual WebSocket Upgrade is Necessary:
    ==========================================
    This function manually implements WebSocket upgrade to the container because:
    
    1. **Physical Server Separation**:
       - Apache runs on one physical server (web server)
       - Docker containers run on another physical server (Docker host)
       - Flask bridges the communication between these servers
       - Apache cannot directly access container ports
    
    2. **Multi-User Container Orchestration**:
       - Multiple users with multiple containers simultaneously
       - Example: user1-ubuntu-vscode (port 7001), user2-chromium (port 7005)
       - Each container runs on a dynamically assigned port (7000-8000 range)
       - Port assignment stored in database, queried by Flask
    
    3. **SSL Certificate Mismatch**: 
       - Public-facing: Apache uses Let's Encrypt (trusted wildcard certificate)
       - Container: Kasm uses self-signed certificate (untrusted)
       - Flask acts as SSL termination point between trusted and untrusted certificates
    
    4. **Dynamic Port Mapping**:
       - Port determined by database lookup: username + desktop_type → container_id → port
       - Apache has no database access or knowledge of container ports
       - Only Flask can route to the correct container
    
    5. **Security**:
       - SSL verification must be disabled for container connections (self-signed certs)
       - This is safe because containers are on isolated Docker host
       - KASM_VERIFY_SSL=false allows this while maintaining public SSL security
    
    Architecture:
    =============
    Browser → Apache (wss:// with Let's Encrypt cert) → 
    Flask (ws:// localhost) → [Network] →
    Docker Host: Container (wss:// with self-signed cert)
    
    Args:
        ws: gevent-websocket WebSocket object from request.environ['wsgi.websocket']
        container: Container object with connection details
        use_ssl: Whether to use SSL for container connection (based on KASM_CONTAINER_PROTOCOL)
    """
    import gevent
    from gevent import socket as green_socket
    
    current_app.logger.info(f"Establishing WebSocket proxy to container port {container.host_port}")
    
    # Get VNC credentials
    vnc_user = os.environ.get('VNC_USER', 'kasm_user')
    vnc_password = os.environ.get('VNC_PASSWORD', 'password')
    
    sock = None
    
    # Connect to the container's WebSocket endpoint
    try:
        # Create socket connection to container
        print(f"[WEBSOCKET DEBUG] Attempting to connect to container at localhost:{container.host_port}")
        current_app.logger.info(f"Attempting to connect to container at localhost:{container.host_port}")
        sock = green_socket.socket(green_socket.AF_INET, green_socket.SOCK_STREAM)
        # Set socket timeout for connection
        sock.settimeout(10)
        try:
            sock.connect(('localhost', container.host_port))
            print(f"[WEBSOCKET DEBUG] Successfully connected to container port {container.host_port}")
            current_app.logger.info(f"Successfully connected to container port {container.host_port}")
        except Exception as connect_error:
            current_app.logger.error(f"Failed to connect to container port {container.host_port}: {connect_error}")
            try:
                ws.close(1011, "Cannot connect to container")
            except Exception:
                pass
            return None
        # Remove timeout after connection is established
        sock.settimeout(None)
        
        # Wrap with SSL if needed
        if use_ssl:
            context = ssl.create_default_context()
            # For localhost container connections, we need to disable verification
            # as Kasm containers use self-signed certificates
            # Security note: This is acceptable for localhost-only connections
            # where the container is on the same host
            verify_ssl = os.environ.get('KASM_VERIFY_SSL', 'false').lower() == 'true'
            if not verify_ssl:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname='localhost')
        
        # Send WebSocket upgrade request to container
        credentials = base64.b64encode(f"{vnc_user}:{vnc_password}".encode()).decode()
        # KasmVNC expects WebSocket at root path /, not /websockify
        upgrade_request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: localhost:{container.host_port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Authorization: Basic {credentials}\r\n"
            f"\r\n"
        )
        sock.sendall(upgrade_request.encode())
        
        # Read the upgrade response from container
        # Limit response size to prevent memory exhaustion attacks
        MAX_HANDSHAKE_SIZE = 8192  # 8KB should be sufficient for WebSocket handshake
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                current_app.logger.error("Container closed connection during WebSocket handshake")
                # Close the client WebSocket with a proper close frame
                try:
                    ws.close(1011, "Container connection failed")
                except Exception:
                    pass
                return None
            response += chunk
            if len(response) > MAX_HANDSHAKE_SIZE:
                current_app.logger.error("WebSocket handshake response too large")
                try:
                    ws.close(1009, "Handshake too large")
                except Exception:
                    pass
                return None
        
        # Check if upgrade was successful
        response_status = response.split(b"\r\n")[0]
        print(f"[WEBSOCKET DEBUG] Container response: {response_status}")
        if b"101" not in response_status:
            print(f"[WEBSOCKET DEBUG] ✗ Container rejected upgrade: {response[:200]}")
            current_app.logger.error(f"Container did not accept WebSocket upgrade: {response[:200]}")
            # Close the client WebSocket with a proper close frame
            try:
                ws.close(1002, "Container rejected connection")
            except Exception:
                pass
            return None
        print(f"[WEBSOCKET DEBUG] ✓ Container accepted upgrade, starting proxy")
        
        current_app.logger.info("WebSocket upgrade successful, starting bidirectional proxy")
        
        # Proxy data between client and container
        def proxy_client_to_container():
            """Forward data from client WebSocket to container socket"""
            try:
                while True:
                    message = ws.receive()
                    if message is None:
                        current_app.logger.debug("Client closed WebSocket connection")
                        break
                    sock.sendall(message)
            except Exception as e:
                current_app.logger.debug(f"Client to container proxy ended: {e}")
            finally:
                try:
                    sock.shutdown(green_socket.SHUT_WR)
                except Exception:
                    pass
        
        def proxy_container_to_client():
            """Forward data from container socket to client WebSocket"""
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        current_app.logger.debug("Container closed connection")
                        break
                    ws.send(data)
            except Exception as e:
                current_app.logger.debug(f"Container to client proxy ended: {e}")
        
        # Start bidirectional proxying in separate greenlets
        client_to_container = gevent.spawn(proxy_client_to_container)
        container_to_client = gevent.spawn(proxy_container_to_client)
        
        # Wait for BOTH directions to complete with timeout (WEBSOCKET_PROXY_TIMEOUT)
        # Note: joinall with timeout will stop waiting but NOT interrupt the greenlets
        # This ensures proper cleanup before closing while preventing indefinite hangs
        gevent.joinall([client_to_container, container_to_client], timeout=WEBSOCKET_PROXY_TIMEOUT)
        
        # Check if any greenlet is still running after timeout
        # If so, kill them and wait briefly for cleanup to complete
        if not client_to_container.ready():
            current_app.logger.warning("Client to container greenlet timed out, killing...")
            client_to_container.kill(block=False)
            gevent.sleep(GREENLET_CLEANUP_WAIT)
        if not container_to_client.ready():
            current_app.logger.warning("Container to client greenlet timed out, killing...")
            container_to_client.kill(block=False)
            gevent.sleep(GREENLET_CLEANUP_WAIT)
        
        # Close WebSocket with proper status code (1000 = normal closure)
        # This prevents code 1005 ("no status received")
        try:
            ws.close(1000, "Connection closed normally")
        except Exception:
            pass
        
        # Clean up container socket
        try:
            sock.close()
        except Exception:
            pass
        
        current_app.logger.info("WebSocket proxy connection closed normally")
        # Don't return an HTTP response after WebSocket is closed
        # The connection is already closed, just return None
        return None
        
    except Exception as e:
        current_app.logger.error(f"Error in WebSocket proxy: {str(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            # Try to close the WebSocket with an error code
            ws.close(1011, "Internal server error")
        except Exception:
            pass
        # Clean up socket if it was created
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def _return_websocket_handshake(container, use_ssl):
    """
    Handle WebSocket upgrade when Apache is tunneling with ws:// protocol
    
    When Apache uses RewriteRule with ws://, it tunnels the TCP connection but Flask's
    gevent-websocket doesn't see the wsgi.websocket object. In this case, Flask receives
    the upgrade headers but must handle the WebSocket at the HTTP level.
    
    The solution is to return HTTP 101 Switching Protocols and then handle the raw socket.
    However, since Flask/gevent-websocket doesn't easily expose the raw socket, we need
    to return an error that tells the client to use a different endpoint or approach.
    """
    current_app.logger.error(
        "WebSocket upgrade request without wsgi.websocket object. "
        "This indicates Apache is using RewriteRule with ws:// which doesn't work with gevent-websocket. "
        f"Container: {container.container_name}, Port: {container.host_port}"
    )
    
    # Return a 502 Bad Gateway error explaining the configuration issue
    return Response(
        "WebSocket proxy configuration error: Flask cannot handle WebSocket tunneled by Apache. "
        "Please configure Apache to use ProxyPass with upgrade=any parameter instead of RewriteRule.",
        status=502,
        mimetype='text/plain'
    )


@proxy_bp.route('/desktop/<path:proxy_path>/websockify', methods=['GET'])
def proxy_websocket(proxy_path):
    """
    Special handler for WebSocket connections at /desktop/<proxy_path>/websockify
    
    This handles WebSocket connections that include the container path in the URL.
    This is more reliable than the root /websockify endpoint because the container
    is explicitly specified in the URL rather than inferred from Referer/session.
    """
    current_app.logger.info(f"WebSocket request at /desktop/{proxy_path}/websockify")
    
    container = Container.get_by_proxy_path(proxy_path)
    
    if not container:
        current_app.logger.warning(f"No running container found for websocket proxy path: {proxy_path}")
        return Response("Container not found or not running", status=404)
    
    if not container.host_port:
        current_app.logger.error(f"Container {container.container_name} has no host port assigned")
        return Response("Container port not available", status=500)
    
    # Update last accessed time
    container.last_accessed = datetime.now(timezone.utc)
    db.session.commit()
    
    # Determine protocol based on environment variable
    container_protocol = os.environ.get('KASM_CONTAINER_PROTOCOL', 'https')
    use_ssl = container_protocol == 'https'
    
    current_app.logger.info(f"Proxying WebSocket to container {container.container_name} on port {container.host_port}")
    
    # Check if this is a WebSocket upgrade request
    ws = request.environ.get('wsgi.websocket')
    is_websocket = ws is not None or (
        request.headers.get('Upgrade', '').lower() == 'websocket' and
        'upgrade' in request.headers.get('Connection', '').lower()
    )
    
    # If this is a WebSocket upgrade request and we have a WebSocket object
    if ws:
        current_app.logger.info("Handling WebSocket with gevent-websocket")
        return _proxy_websocket_with_gevent(ws, container, use_ssl)
    elif is_websocket:
        # WebSocket upgrade request but no ws object
        current_app.logger.error(
            "WebSocket upgrade request detected but wsgi.websocket is not available! "
            "This indicates a server configuration issue."
        )
        return Response(
            "WebSocket not supported - server configuration error.",
            status=500,
            mimetype='text/plain'
        )
    else:
        # Regular HTTP request (for testing/debugging)
        current_app.logger.debug(f"Regular HTTP request to /desktop/{proxy_path}/websockify (not WebSocket)")
        return Response(
            f"This endpoint is for WebSocket connections only. "
            f"Container: {container.container_name}, Port: {container.host_port}",
            status=200,
            mimetype='text/plain'
        )
"""
New WebSocket route using flask-sock (modern, maintained library)

This replaces the old gevent-websocket implementation which is unmaintained since 2017
and has compatibility issues with modern Python/gevent.
"""

# Add this at the END of proxy_routes.py after all other routes

@sock.route('/websockify')
def websockify_sock(ws):
    """
    Handle WebSocket connections using flask-sock
    
    With flask-sock, the WebSocket handshake is handled automatically by the library.
    This function is called AFTER the handshake completes, with a connected WebSocket object.
    
    Args:
        ws: simple-websocket WebSocket object (not gevent-websocket)
    """
    import sys
    print("=" * 80, flush=True)
    print("[FLASK-SOCK] WebSocket route handler called!", flush=True)
    print(f"Host: {request.headers.get('Host')}", flush=True)
    print("=" * 80, flush=True)
    sys.stdout.flush()
    
    referer = request.headers.get('Referer', '')
    host = request.headers.get('Host', '')
    current_app.logger.info(f"WebSocket connection at /websockify with Host: {host}, Referer: {referer}")
    
    container = None
    
    # PRIORITY 1: Extract container from subdomain in Host header
    if host and '.desktop.hub.mdg-hamburg.de' in host:
        subdomain = host.split('.desktop.hub.mdg-hamburg.de')[0]
        if subdomain and subdomain != 'desktop':
            container = Container.get_by_proxy_path(subdomain)
            if container:
                current_app.logger.info(f"Found container from subdomain: {subdomain} -> {container.container_name}")
            else:
                current_app.logger.error(f"Container not found for subdomain: {subdomain}")
    
    # PRIORITY 2: Try Referer header
    if not container and referer:
        match = re.search(r'/desktop/([^/?#]+)', referer)
        if match:
            referer_proxy_path = match.group(1)
            if not is_asset_path(referer_proxy_path):
                container = Container.get_by_proxy_path(referer_proxy_path)
                if container:
                    current_app.logger.info(f"Found container from Referer: {referer_proxy_path}")
    
    # PRIORITY 3: Try session
    if not container:
        session_container_name = session.get('current_container')
        if session_container_name:
            container = Container.get_by_proxy_path(session_container_name)
            if container:
                current_app.logger.info(f"Found container from session: {session_container_name}")
    
    if not container:
        current_app.logger.error("No container found for WebSocket connection")
        ws.close(reason="Container not found")
        return
    
    if not container.host_port:
        current_app.logger.error(f"Container {container.container_name} has no host port")
        ws.close(reason="Container port not available")
        return
    
    # Get container connection settings
    use_ssl = os.environ.get('KASM_CONTAINER_PROTOCOL', 'https') == 'https'
    
    # Proxy the WebSocket connection
    _proxy_websocket_flask_sock(ws, container, use_ssl, host)


def _proxy_websocket_flask_sock(client_ws, container, use_ssl, host=None):
    """
    Raw socket-level TCP tunnel for WebSocket
    
    After the browser's WebSocket handshake with Flask completes, we get access to the
    underlying socket. We connect to KasmVNC and tunnel raw TCP data bidirectionally.
    
    Args:
        client_ws: simple-websocket WebSocket object from flask-sock
        container: Container object  
        use_ssl: Whether to use SSL for container connection
    """
    import socket as std_socket
    import ssl as ssl_module
    from gevent import spawn
    import select
    
    current_app.logger.info(f"Starting socket-level TCP tunnel to container")
    
    container_sock = None
    
    try:
        # Get container IP from Docker
        container_ip = None
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', 
                 container.container_name],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                container_ip = result.stdout.strip()
                current_app.logger.info(f"Container IP: {container_ip}")
        except Exception as e:
            current_app.logger.warning(f"Could not get container IP: {e}")
        
        if not container_ip:
            current_app.logger.error("Could not determine container IP")
            return
        
        # Connect to container's WebSocket/HTTP port (6901)
        container_port = 6901
        current_app.logger.info(f"Connecting to container at {container_ip}:{container_port}")
        container_sock = std_socket.socket(std_socket.AF_INET, std_socket.SOCK_STREAM)
        container_sock.settimeout(10)
        container_sock.connect((container_ip, container_port))
        container_sock.settimeout(None)
        
        # Wrap with SSL
        if use_ssl:
            context = ssl_module.create_default_context()
            verify_ssl = os.environ.get('KASM_VERIFY_SSL', 'false').lower() == 'true'
            if not verify_ssl:
                context.check_hostname = False
                context.verify_mode = ssl_module.CERT_NONE
            container_sock = context.wrap_socket(container_sock, server_hostname=container_ip)
            current_app.logger.info("SSL connection established")
        
        # Send WebSocket upgrade to KasmVNC
        import base64
        vnc_user = os.environ.get('VNC_USER', 'kasm_user')
        vnc_password = os.environ.get('VNC_PASSWORD', 'password')
        ws_key = base64.b64encode(os.urandom(16)).decode()
        credentials = base64.b64encode(f"{vnc_user}:{vnc_password}".encode()).decode()
        
        upgrade_request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {container_ip}:{container_port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Authorization: Basic {credentials}\r\n"
            f"\r\n"
        )
        
        current_app.logger.info(f"Sending WebSocket upgrade to KasmVNC")
        container_sock.sendall(upgrade_request.encode())
        
        # Read upgrade response  
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = container_sock.recv(1024)
            if not chunk:
                raise Exception("Connection closed during handshake")
            response += chunk
        
        status_line = response.split(b'\r\n')[0].decode()
        current_app.logger.info(f"KasmVNC response: {status_line}")
        
        # If upgrade failed, close immediately - don't relay HTML to noVNC!
        if not status_line.startswith('HTTP/1.1 101'):
            current_app.logger.error(f"KasmVNC rejected WebSocket upgrade: {status_line}")
            current_app.logger.error("Cannot proxy - KasmVNC requires direct browser connection")
            return
        
        current_app.logger.info("✓ WebSocket upgrade successful!")
        
        # Use client_ws.receive() and client_ws.send() for WebSocket framing
        current_app.logger.info("Starting WebSocket frame relay")
        
        # Raw bidirectional relay using WebSocket API
        def client_to_container():
            """Receive WebSocket frames from client, send binary to container"""
            try:
                while True:
                    data = client_ws.receive()  # Receives decoded WebSocket data
                    if data is None:
                        break
                    # Send raw binary to container (no WebSocket framing)
                    if isinstance(data, bytes):
                        container_sock.sendall(data)
                    elif isinstance(data, str):
                        container_sock.sendall(data.encode('utf-8'))
            except Exception as e:
                pass  # No app context in greenlet
            finally:
                try:
                    container_sock.close()
                except:
                    pass
        
        def container_to_client():
            """Receive binary from container, send as WebSocket frames to client"""
            try:
                while True:
                    data = container_sock.recv(4096)
                    if not data:
                        break
                    # Send as WebSocket binary frame
                    client_ws.send(data)
            except Exception as e:
                pass  # No app context in greenlet
            finally:
                try:
                    client_ws.close()
                except:
                    pass
        
        # Spawn both relay greenlets
        current_app.logger.info("Spawning relay greenlets")
        g1 = spawn(client_to_container)
        g2 = spawn(container_to_client)
        
        # Wait for either to finish
        g1.join()
        g2.join()
        
        current_app.logger.info("TCP tunnel closed")
        
    except Exception as e:
        current_app.logger.error(f"TCP tunnel error: {e}", exc_info=True)
    finally:
        if container_sock:
            try:
                container_sock.close()
            except:
                pass


def _OLD_proxy_websocket_flask_sock(client_ws, container, use_ssl, host=None):
    """
    OLD VERSION - tried to connect to KasmVNC's HTTP/WebSocket port
    This didn't work because KasmVNC rejected our upgrade request.
    """
    import socket as std_socket
    import ssl
    import base64
    from gevent import spawn
    from gevent.socket import wait_read, wait_write
    
    current_app.logger.info(f"Proxying WebSocket to container port {container.host_port}")
    
    # Get VNC credentials
    vnc_user = os.environ.get('VNC_USER', 'kasm_user')
    vnc_password = os.environ.get('VNC_PASSWORD', 'password')
    
    sock = None
    
    try:
        # Connect to container using gevent socket
        current_app.logger.info(f"Connecting to container at localhost:{container.host_port}")
        sock = std_socket.socket(std_socket.AF_INET, std_socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(('localhost', container.host_port))
        sock.settimeout(None)
        
        # Wrap with SSL if needed
        if use_ssl:
            context = ssl.create_default_context()
            verify_ssl = os.environ.get('KASM_VERIFY_SSL', 'false').lower() == 'true'
            if not verify_ssl:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname='localhost')
            current_app.logger.info("SSL wrap successful")
        
        # Send WebSocket upgrade to container
        credentials = base64.b64encode(f"{vnc_user}:{vnc_password}".encode()).decode()
        ws_key = base64.b64encode(os.urandom(16)).decode()
        
        # KasmVNC requires Basic authentication for WebSocket
        upgrade_request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: localhost:{container.host_port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Authorization: Basic {credentials}\r\n"
            f"\r\n"
        )
        
        current_app.logger.info(f"Sending WebSocket upgrade with auth: GET /, Key: {ws_key}")
        current_app.logger.info(f"Full credentials: {credentials}")
        current_app.logger.info(f"VNC user: {vnc_user}, VNC pass: {vnc_password}")
        current_app.logger.info(f"Request (repr): {repr(upgrade_request)}")
        sock.sendall(upgrade_request.encode())
        
        # Read upgrade response
        current_app.logger.info("Waiting for container upgrade response")
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                current_app.logger.error("Container closed connection during handshake")
                return
            response += chunk
            if len(response) > 8192:
                current_app.logger.error("Handshake response too large")
                return
        
        # Log first few lines of response
        response_lines = response.split(b"\r\n")[:5]
        for line in response_lines:
            current_app.logger.info(f"  Response line: {line}")
        
        # Check upgrade response
        status_line = response.split(b"\r\n")[0].decode('utf-8', errors='ignore')
        current_app.logger.info(f"Container response: {status_line}")
        
        if b"101" not in response.split(b"\r\n")[0]:
            current_app.logger.error(f"Container rejected upgrade (expected 101): {response[:300]}")
            return
        
        current_app.logger.info("WebSocket upgrade successful, starting bidirectional proxy")
        
        # Proxy data bidirectionally using gevent
        def client_to_container():
            try:
                while True:
                    message = client_ws.receive()
                    if message is None:
                        current_app.logger.info("Client closed connection")
                        break
                    sock.sendall(message)
            except Exception as e:
                current_app.logger.info(f"Client to container ended: {e}")
            finally:
                try:
                    sock.shutdown(std_socket.SHUT_WR)
                except:
                    pass
        
        def container_to_client():
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        current_app.logger.info("Container closed connection")
                        break
                    client_ws.send(data)
            except Exception as e:
                current_app.logger.info(f"Container to client ended: {e}")
            finally:
                try:
                    client_ws.close()
                except:
                    pass
        
        # Start both directions using gevent greenlets
        g1 = spawn(client_to_container)
        g2 = spawn(container_to_client)
        g1.join()
        g2.join()
        
        current_app.logger.info("WebSocket proxy completed")
        
    except Exception as e:
        current_app.logger.error(f"WebSocket proxy error: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        try:
            client_ws.close(reason=str(e))
        except:
            pass
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass
