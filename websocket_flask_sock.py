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
    _proxy_websocket_flask_sock(ws, container, use_ssl)


def _proxy_websocket_flask_sock(client_ws, container, use_ssl):
    """
    Proxy WebSocket connection using flask-sock/simple-websocket
    
    Args:
        client_ws: simple-websocket WebSocket object from flask-sock
        container: Container object
        use_ssl: Whether to use SSL for container connection
    """
    import socket as std_socket
    import ssl
    import base64
    import threading
    
    current_app.logger.info(f"Proxying WebSocket to container port {container.host_port}")
    
    # Get VNC credentials
    vnc_user = os.environ.get('VNC_USER', 'kasm_user')
    vnc_password = os.environ.get('VNC_PASSWORD', 'password')
    
    sock = None
    
    try:
        # Connect to container
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
        
        # Send WebSocket upgrade to container
        credentials = base64.b64encode(f"{vnc_user}:{vnc_password}".encode()).decode()
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
        
        # Read upgrade response
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                current_app.logger.error("Container closed connection during handshake")
                client_ws.close(reason="Container connection failed")
                return
            response += chunk
            if len(response) > 8192:
                current_app.logger.error("Handshake response too large")
                client_ws.close(reason="Handshake failed")
                return
        
        # Check upgrade response
        if b"101" not in response.split(b"\r\n")[0]:
            current_app.logger.error(f"Container rejected upgrade: {response[:200]}")
            client_ws.close(reason="Container rejected connection")
            return
        
        current_app.logger.info("WebSocket upgrade successful, starting proxy")
        
        # Proxy data bidirectionally
        def client_to_container():
            try:
                while True:
                    message = client_ws.receive()
                    if message is None:
                        break
                    sock.sendall(message)
            except Exception as e:
                current_app.logger.debug(f"Client to container ended: {e}")
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
                        break
                    client_ws.send(data)
            except Exception as e:
                current_app.logger.debug(f"Container to client ended: {e}")
            finally:
                try:
                    client_ws.close()
                except:
                    pass
        
        # Start both directions in threads
        t1 = threading.Thread(target=client_to_container)
        t2 = threading.Thread(target=container_to_client)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
    except Exception as e:
        current_app.logger.error(f"WebSocket proxy error: {e}")
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
