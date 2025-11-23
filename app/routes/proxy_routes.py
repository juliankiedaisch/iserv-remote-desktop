from flask import Blueprint, request, Response, current_app, session
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
    referer = request.headers.get('Referer', '')
    current_app.logger.info(f"WebSocket request at /websockify with Referer: {referer}")
    current_app.logger.debug(f"Request headers: {dict(request.headers)}")
    
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
            current_app.logger.info("wsgi.websocket object is NOT available (may be handled by Apache)")
    else:
        current_app.logger.info("NOT a WebSocket upgrade request")
    
    container = None
    
    # Try to find container from Referer first
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
            
            # Validate extracted path length
            if len(referer_proxy_path) > 255:  # Max reasonable proxy path length
                current_app.logger.warning(f"Extracted proxy path too long: {len(referer_proxy_path)} chars")
                return Response("Invalid container path", status=400)
            
            # Check if this referer path is NOT an asset path
            if not is_asset_path(referer_proxy_path):
                # Find the container
                container = Container.get_by_proxy_path(referer_proxy_path)
                if container:
                    current_app.logger.debug(f"Found container from Referer: {referer_proxy_path}")
            else:
                current_app.logger.debug(f"Referer path is an asset: {referer_proxy_path}, trying session")
    
    # If no container found from Referer, try session
    if not container:
        session_container_name = session.get('current_container')
        if session_container_name:
            current_app.logger.debug(f"Trying container from session for WebSocket: {session_container_name}")
            container = Container.get_by_proxy_path(session_container_name)
            if container:
                current_app.logger.debug(f"Found container from session for WebSocket: {session_container_name}")
    
    if not container:
        current_app.logger.warning(f"No running container found for websocket (Referer: {referer})")
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
    
    # If this is a WebSocket upgrade request and we have a WebSocket object from eventlet/gunicorn
    if ws:
        current_app.logger.info("Handling WebSocket with eventlet")
        return _proxy_websocket_with_eventlet(ws, container, use_ssl)
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


def _proxy_websocket_with_eventlet(ws, container, use_ssl):
    """
    Proxy WebSocket connection between client and container using gevent
    
    Note: Despite the function name referencing 'eventlet', this implementation
    uses gevent-websocket which is the proper WebSocket handler when running with
    gunicorn + GeventWebSocketWorker or the gevent-websocket development server.
    
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
        current_app.logger.info(f"Attempting to connect to container at localhost:{container.host_port}")
        sock = green_socket.socket(green_socket.AF_INET, green_socket.SOCK_STREAM)
        # Set socket timeout for connection
        sock.settimeout(10)
        try:
            sock.connect(('localhost', container.host_port))
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
        upgrade_request = (
            f"GET /websockify HTTP/1.1\r\n"
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
        if b"101" not in response.split(b"\r\n")[0]:
            current_app.logger.error(f"Container did not accept WebSocket upgrade: {response[:200]}")
            # Close the client WebSocket with a proper close frame
            try:
                ws.close(1002, "Container rejected connection")
            except Exception:
                pass
            return None
        
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
    Return a WebSocket handshake response for Apache/Nginx to intercept and upgrade
    
    This is used when running with a dev server that doesn't support WebSocket natively.
    Apache/Nginx should see this response and establish the WebSocket connection.
    """
    # For now, redirect to the container-specific WebSocket endpoint
    # This allows Apache to properly route the WebSocket connection
    protocol = 'https' if use_ssl else 'http'
    redirect_url = f"{protocol}://localhost:{container.host_port}/websockify"
    
    current_app.logger.debug(f"Redirecting WebSocket to: {redirect_url}")
    
    # Return a 307 Temporary Redirect which preserves the request method and body
    # This allows Apache to re-attempt the WebSocket upgrade to the container
    return Response(
        f"Redirecting WebSocket connection to container",
        status=307,
        headers={'Location': redirect_url}
    )


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
