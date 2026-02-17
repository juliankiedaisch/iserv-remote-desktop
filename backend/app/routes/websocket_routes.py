"""
WebSocket routes for real-time container status updates.

This module provides Socket.IO-based WebSocket endpoints for:
- Container status updates
- Container creation/deletion notifications
- Real-time dashboard updates

Uses Flask-SocketIO for WebSocket support with gevent as the async mode.
"""

from flask import Blueprint, current_app
from flask_socketio import SocketIO, emit, join_room, leave_room
from app.models.oauth_session import OAuthSession
from datetime import datetime, timezone

websocket_bp = Blueprint('websocket', __name__)

# SocketIO instance will be initialized in create_app
socketio = None


def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    global socketio
    socketio = SocketIO(
        app,
        cors_allowed_origins=app.config.get('FRONTEND_URL', '*'),
        async_mode='gevent',
        path='/ws'
    )
    register_handlers()
    return socketio


def register_handlers():
    """Register Socket.IO event handlers"""
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Handle client connection"""
        session_id = None
        if auth:
            session_id = auth.get('session_id')
        
        if not session_id:
            current_app.logger.warning("WebSocket connection without session_id")
            return False  # Reject connection
        
        # Validate session
        oauth_session = OAuthSession.query.filter_by(id=session_id).first()
        if not oauth_session:
            current_app.logger.warning(f"WebSocket: Invalid session_id: {session_id}")
            return False
        
        # Check if session is expired
        current_time = datetime.now(timezone.utc)
        expires_at = oauth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < current_time:
            current_app.logger.warning(f"WebSocket: Expired session: {session_id}")
            return False
        
        # Join room based on user_id for targeted updates
        user_id = oauth_session.user_id
        join_room(f"user_{user_id}")
        
        # Join admin room if user is admin
        if oauth_session.user and oauth_session.user.is_admin:
            join_room("admins")
        
        current_app.logger.info(f"WebSocket: User {oauth_session.user.username} connected")
        return True
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        current_app.logger.info("WebSocket: Client disconnected")
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        """Subscribe to a specific container's updates"""
        container_id = data.get('container_id')
        if container_id:
            join_room(f"container_{container_id}")
            current_app.logger.debug(f"WebSocket: Subscribed to container_{container_id}")
    
    @socketio.on('unsubscribe')
    def handle_unsubscribe(data):
        """Unsubscribe from a specific container's updates"""
        container_id = data.get('container_id')
        if container_id:
            leave_room(f"container_{container_id}")
            current_app.logger.debug(f"WebSocket: Unsubscribed from container_{container_id}")
    
    @socketio.on('container_heartbeat')
    def handle_container_heartbeat(data):
        """
        Handle heartbeat from viewer to track container activity.
        Updates the container's last_accessed timestamp to prevent idle shutdown.
        
        Args:
            data: Dict containing 'proxy_path' or 'container_id'
        """
        try:
            from app.models.containers import Container
            from app import db
            
            proxy_path = data.get('proxy_path')
            container_id = data.get('container_id')
            
            if not proxy_path and not container_id:
                current_app.logger.warning("WebSocket heartbeat without proxy_path or container_id")
                return
            
            # Find container by proxy_path or container_id
            if proxy_path:
                container = Container.query.filter_by(proxy_path=proxy_path).first()
            else:
                container = Container.query.filter_by(id=container_id).first()
            
            if not container:
                current_app.logger.warning(f"WebSocket heartbeat: Container not found (proxy_path={proxy_path}, id={container_id})")
                return
            
            # Update last_accessed timestamp
            container.last_accessed = datetime.now(timezone.utc)
            db.session.commit()
            
            current_app.logger.debug(f"Container heartbeat: Updated last_accessed for {container.container_name}")
            
        except Exception as e:
            current_app.logger.error(f"Error handling container heartbeat: {str(e)}")
            from app import db
            db.session.rollback()


def emit_container_status(container, user_id=None):
    """
    Emit container status update to connected clients
    
    Args:
        container: Container model instance
        user_id: Optional user_id to target specific user
    """
    if not socketio:
        return
    
    status_data = {
        'container_id': container.id,
        'status': container.status,
        'docker_status': container.status,
        'desktop_type': container.desktop_type,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Emit to specific user
    if user_id:
        socketio.emit('container_status', status_data, room=f"user_{user_id}")
    
    # Also emit to admins
    socketio.emit('container_status', status_data, room="admins")
    
    # Emit to container-specific room
    socketio.emit('container_status', status_data, room=f"container_{container.id}")


def emit_container_created(container, user_id=None):
    """
    Emit container created event
    
    Args:
        container: Container model instance
        user_id: Optional user_id to target specific user
    """
    if not socketio:
        return
    
    event_data = {
        'container_id': container.id,
        'container_name': container.container_name,
        'desktop_type': container.desktop_type,
        'proxy_path': container.proxy_path,
        'status': container.status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if user_id:
        socketio.emit('container_created', event_data, room=f"user_{user_id}")
    
    socketio.emit('container_created', event_data, room="admins")


def emit_container_stopped(container, user_id=None):
    """
    Emit container stopped event
    
    Args:
        container: Container model instance
        user_id: Optional user_id to target specific user
    """
    if not socketio:
        return
    
    event_data = {
        'container_id': container.id,
        'container_name': container.container_name,
        'desktop_type': container.desktop_type,
        'status': 'stopped',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if user_id:
        socketio.emit('container_stopped', event_data, room=f"user_{user_id}")
    
    socketio.emit('container_stopped', event_data, room="admins")


def emit_image_pull_event(event_type, data, user_id=None):
    """
    Emit image pull events for real-time progress updates
    
    Args:
        event_type: Type of event (image_pull_started, image_pull_progress, 
                    image_pull_completed, image_pull_error)
        data: Event data dict
        user_id: Optional user_id to target specific user
    """
    if not socketio:
        return
    
    event_data = {
        **data,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Emit to specific user if provided
    if user_id:
        socketio.emit(event_type, event_data, room=f"user_{user_id}")
    
    # Always emit to admins for image pull events
    socketio.emit(event_type, event_data, room="admins")


def emit_template_refresh_event(event_type, data, user_id=None):
    """
    Emit template refresh events for real-time progress updates
    
    Args:
        event_type: Type of event (template_refresh_started, template_refresh_progress, 
                    template_refresh_completed, template_refresh_error)
        data: Event data dict
        user_id: Optional user_id to target specific user
    """
    if not socketio:
        return
    
    event_data = {
        **data,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Emit to specific user if provided
    if user_id:
        socketio.emit(event_type, event_data, room=f"user_{user_id}")
    
    # Always emit to admins for template refresh events
    socketio.emit(event_type, event_data, room="admins")

