from functools import wraps
from flask import request, jsonify, current_app
from app.models.oauth_session import OAuthSession
from datetime import datetime, timezone, timedelta
from app import db
import requests, os

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = None
        
        # Check query parameter
        session_id = request.args.get('session_id')
        
        # Check X-Session-ID header
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        # Check Authorization header with Bearer token
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            print("No session ID provided")
            return jsonify({'error': 'Authentication required'}), 401
            
        oauth_session = OAuthSession.get_by_session_id(session_id)
        if not oauth_session:
            print(f"Invalid session ID requested: {session_id}")
            return jsonify({'error': 'Invalid session'}), 401

        # Ensure expires_at is timezone-aware
        expires_at = oauth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        # Check if session is expired
        if expires_at < datetime.now(timezone.utc):
            print(f"Session expired for user {oauth_session.user.username}")
            
            # Attempt to renew the session using refresh token
            if oauth_session.refresh_token:
                try:
                    # Get OAuth configuration from environment or config
                    client_id = os.environ.get('OAUTH_CLIENT_ID')
                    client_secret = os.environ.get('OAUTH_CLIENT_SECRET')
                    token_endpoint = os.environ.get('OAUTH_TOKEN_URL')
                    
                    # Prepare token refresh request
                    refresh_data = {
                        'client_id': client_id,
                        'client_secret': client_secret,
                        'grant_type': 'refresh_token',
                        'refresh_token': oauth_session.refresh_token
                    }
                    
                    # Make request to OAuth server
                    response = requests.post(token_endpoint, data=refresh_data, timeout=10)
                    
                    if response.status_code == 200:
                        token_data = response.json()
                        
                        # Update session with new tokens
                        oauth_session.access_token = token_data.get('access_token')
                        
                        # Update refresh token if provided
                        if 'refresh_token' in token_data:
                            oauth_session.refresh_token = token_data.get('refresh_token')
                        
                        oauth_session.expires_at = datetime.now(timezone.utc) + timedelta(hours=12)
                        
                        # Update last accessed time
                        oauth_session.last_accessed = datetime.now(timezone.utc)
                        
                        # Save changes to database
                        db.session.commit()
                        
                        print(f"Session renewed for user {oauth_session.user.username}")
                    else:
                        print(f"Failed to renew session: {response.status_code} {response.text}")
                        return jsonify({'error': 'Session expired and renewal failed', 'renewal_required': True}), 401
                        
                except Exception as e:
                    print(f"Error renewing session: {str(e)}")
                    return jsonify({'error': 'Session expired and renewal failed', 'renewal_required': True}), 401
            else:
                # No refresh token available
                return jsonify({'error': 'Session expired and no refresh token available', 'renewal_required': True}), 401
        else:
            # Session is still valid, update last accessed time
            oauth_session.last_accessed = datetime.now(timezone.utc)
            db.session.commit()
        
        # Store the oauth session in the request object for access in routes
        request.oauth_session = oauth_session
        request.user = oauth_session.user            
        
        # Pass user info to the route
        user = {
            'session_id': oauth_session.id,
            'user_id': oauth_session.user.id,
            'username': oauth_session.user.username,
            'email': oauth_session.user.email,
            'role': oauth_session.user.role
        }
        
        return f(user, *args, **kwargs)
    return decorated_function

def check_auth(f):
    """Middleware to check authentication but not require it"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = None
        
        # Check various places for the session ID
        session_id = request.args.get('session_id')
        
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if session_id:
            oauth_session = OAuthSession.get_by_session_id(session_id)
            if oauth_session and oauth_session.expires_at > datetime.now(timezone.utc):
                # Store the session in the request for later use
                request.oauth_session = oauth_session
                request.user = oauth_session.user
                
                # Update last accessed time
                oauth_session.last_accessed = datetime.now(timezone.utc)
                from app import db
                db.session.commit()
                
                g.user_authenticated = True
                return f(*args, **kwargs)
        
        # User is not authenticated but we'll still call the function
        g.user_authenticated = False
        return f(*args, **kwargs)
    
    return decorated_function

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = None
        
        # Check query parameter
        session_id = request.args.get('session_id')
        
        # Check X-Session-ID header
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        # Check Authorization header with Bearer token
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            return jsonify({'error': 'Authentication required'}), 401
            
        oauth_session = OAuthSession.get_by_session_id(session_id)
        if not oauth_session:
            return jsonify({'error': 'Invalid session'}), 401
            
        # Check if session is expired
        if oauth_session.expires_at < datetime.now(timezone.utc):
            return jsonify({'error': 'Session expired'}), 401
            
        # Check if user is admin
        if oauth_session.role != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403
            
        # Pass user info to the route
        user = {
            'session_id': oauth_session.id,
            'user_id': oauth_session.user_id,
            'username': oauth_session.username,
            'email': oauth_session.email,
            'role': oauth_session.role
        }
        
        return f(user, *args, **kwargs)
    return decorated_function

def require_teacher(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = None
        
        # Check query parameter
        session_id = request.args.get('session_id')
        
        # Check X-Session-ID header
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        # Check Authorization header with Bearer token
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            return jsonify({'error': 'Authentication required'}), 401
            
        oauth_session = OAuthSession.get_by_session_id(session_id)
        if not oauth_session:
            return jsonify({'error': 'Invalid session'}), 401
    
        # Check if user is admin or teacher
        if oauth_session.user.role != 'admin' and oauth_session.user.role != 'teacher' :
            return jsonify({'error': 'Admin or Teacher privileges required'}), 403
            
        # Pass user info to the route
        user = {
            'session_id': oauth_session.id,
            'user_id': oauth_session.user_id,
            'username': oauth_session.user.username,
            'email': oauth_session.user.email,
            'role': oauth_session.user.role
        }
        
        return f(*args, **kwargs)
    return decorated_function