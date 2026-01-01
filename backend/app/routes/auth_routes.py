from flask import Blueprint, redirect, session, url_for, jsonify, request, current_app
from app import oauth, db
from app.models.oauth_session import OAuthSession
from werkzeug.exceptions import Unauthorized
from datetime import datetime, timezone
import secrets  # Add this import for generating secure random strings
from authlib.integrations.requests_client import OAuth2Session
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    """Redirect to OAuth provider login with explicit state handling"""
    # Generate state
    state = secrets.token_urlsafe(32)
    
    # Store state in session
    session['oauth_state'] = state
    session.modified = True
    
    current_app.logger.info(f"OAuth Login - Generated state: {state}")
    current_app.logger.info(f"OAuth Login - Session state set to: {session.get('oauth_state')}")
    
    # Hardcode the full URL for reliability
    callback_url = os.environ.get('OAUTH_REDIRECT_URI')
    print(callback_url)
    
    # Create redirect response
    response = oauth.oauth_provider.authorize_redirect(
        redirect_uri=callback_url,
        state=state
    )
    
    # Set state cookie with same value
    response.set_cookie(
        'oauth_state', 
        state,
        path='/',
        secure=True,
        httponly=True,
        samesite='Lax',
        max_age=600
    )
    
    return response

@auth_bp.route('/authorize')
def authorize():
    """Handle OAuth callback with explicit state validation"""
    try:
        # Check state parameter manually first
        received_state = request.args.get('state')
        cookie_state = request.cookies.get('oauth_state')
        
        current_app.logger.info(f"OAuth Callback - Received state: {received_state}")
        current_app.logger.info(f"OAuth Callback - Cookie state: {cookie_state}")

        if not cookie_state or received_state != cookie_state:
            raise Exception("State parameter mismatch. Possible CSRF attack.")
        
        # Set session state to match received state
        session['oauth_state'] = received_state
        session.modified = True
        # Proceed with token exchange
        token = oauth.oauth_provider.authorize_access_token()
        
        user_info = token.get("userinfo") 
        
        # Extract user data
        user_id = user_info.get('uuid') or user_info.get('id') or user_info.get('sub')
        username = user_info.get('preferred_username') or user_info.get('username') or user_info.get('name')
        email = user_info.get('email')
        
        if not user_id or not username:
            raise Exception("Incomplete user information from OAuth provider")
        # Create session
        oauth_session = OAuthSession.create_session(
            user_id=user_id,
            username=username,
            email=email,
            tokens=token,
            user_data=user_info
        )
        # Redirect to frontend with session token
        redirect_url = f"{current_app.config['FRONTEND_URL']}?session_id={oauth_session.id}"
        response =  redirect(redirect_url)
        response.delete_cookie('oauth_state')
        return response
    
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"OAuth error: {str(e)}")
        
        # Redirect to frontend with error
        error_msg = str(e)
        redirect_url = f"{current_app.config['FRONTEND_URL']}?error={error_msg}"
        return redirect(redirect_url)


@auth_bp.route('/session', methods=['GET'])
def get_session():
    """Validate and return session details with token refresh support"""
    # Check for session ID in different locations
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
        current_app.logger.debug("Session request without session ID")
        return jsonify({'error': 'No session ID provided'}), 400
        
    # Get the session from database with row-level lock
    oauth_session = OAuthSession.query.filter_by(id=session_id).with_for_update().first()
    if not oauth_session:
        current_app.logger.debug(f"Invalid session ID requested: {session_id}")
        return jsonify({'error': 'Invalid session'}), 401
    
    # Check if session is expired
    current_time = datetime.now(timezone.utc)
    # Ensure oauth_session.expires_at is timezone-aware
    expires_at = oauth_session.expires_at
    if expires_at.tzinfo is None:
        # If it's naive, make it aware by assuming it's in UTC
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < current_time:
        current_app.logger.info(f"Session expired for user {oauth_session.user.username}")
        
        if oauth_session.refresh_token:
            try:
                # Create OAuth2Session
                client = OAuth2Session(
                    client_id=oauth.oauth_provider.client_id,
                    client_secret=oauth.oauth_provider.client_secret,
                )
                
                # Refresh the token
                token_data = client.refresh_token(
                    oauth.oauth_provider.access_token_url,  # Use the token URL from your provider
                    refresh_token=oauth_session.refresh_token
                )
                
                # Update session with new tokens
                oauth_session.update_tokens(token_data)
                db.session.commit()
                
                current_app.logger.info(f"Successfully refreshed token for {oauth_session.user.username}")
            except Exception as e:
                current_app.logger.error(f"Token refresh failed: {str(e)}")
                db.session.rollback()
                return jsonify({'error': 'Session expired and refresh failed'}), 401
        else:
            return jsonify({'error': 'Session expired'}), 401
    
    # Update last accessed timestamp
    oauth_session.last_accessed = current_time
    db.session.commit()
    
    # Return session data with user info
    user = oauth_session.user
    return jsonify({
        'session': {
            'id': oauth_session.id,
            'expires_at': oauth_session.expires_at.isoformat()
        },
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'groups': [group.to_dict() for group in user.groups],
            'avatar_url': user.user_data.get('picture') if user.user_data else None
        },
        'authenticated': True
    })


@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """Log out the current user by invalidating their session"""
    try:
        # Get session ID from various possible sources
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
            return jsonify({
                'success': False,
                'message': 'No session ID provided'
            }), 400
            
        # Find the session
        oauth_session = OAuthSession.get_by_session_id(session_id)
        
        if oauth_session:
            # Log the logout
            current_app.logger.info(f"User {oauth_session.user.username} logged out")
            
            # Delete only the session, not the user
            db.session.delete(oauth_session)
            db.session.commit()
        
        # Clear any Flask session data
        session.clear()
        
        # Create response
        response = jsonify({
            'success': True,
            'message': 'Successfully logged out'
        })
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error during logout: {str(e)}'
        }), 500
