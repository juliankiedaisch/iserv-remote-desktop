from flask import Blueprint, redirect, session, url_for, jsonify, request, current_app
from app import oauth, db
from app.models.oauth_session import OAuthSession
from app.i18n import get_message, get_language_from_request
from werkzeug.exceptions import Unauthorized
from datetime import datetime, timezone
import secrets  # Add this import for generating secure random strings
from authlib.integrations.requests_client import OAuth2Session
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    """Redirect to OAuth provider login with explicit state handling"""
    # Log all incoming cookies for debugging
    current_app.logger.info(f"OAuth Login - Incoming cookies: {dict(request.cookies)}")
    
    # Force a completely new session by clearing and regenerating
    session.clear()
    # Force Flask to generate a new session ID
    session.modified = True
    
    # Generate state
    state = secrets.token_urlsafe(32)
    
    # Store state in NEW session
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
    
    # Aggressively clear ALL possible session and oauth_state cookies
    # Try multiple combinations of path/domain to ensure cleanup
    domain = current_app.config.get('SERVER_NAME', request.host.split(':')[0])
    
    # Clear oauth_state cookie with various combinations
    response.delete_cookie('oauth_state', path='/', domain=None)
    response.delete_cookie('oauth_state', path='/', domain=domain)
    response.delete_cookie('oauth_state', path='/api', domain=None)
    response.delete_cookie('oauth_state', path='/api', domain=domain)
    
    # Aggressively clear Flask session cookies with all combinations
    response.delete_cookie('session', path='/', domain=None)
    response.delete_cookie('session', path='/', domain=domain)
    response.delete_cookie('session', path='/api', domain=None)
    response.delete_cookie('session', path='/api', domain=domain)
    
    # Also try clearing with secure flags
    response.set_cookie('session', '', path='/', expires=0, secure=True, httponly=True, samesite='Lax')
    response.set_cookie('session', '', path='/', expires=0, domain=domain, secure=True, httponly=True, samesite='Lax')
    
    current_app.logger.info(f"OAuth Login - Cleared all old cookies, setting new oauth_state")
    
    # Set new oauth_state cookie
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
        # Log all incoming cookies and session state for debugging
        current_app.logger.info(f"OAuth Callback - All cookies: {dict(request.cookies)}")
        current_app.logger.info(f"OAuth Callback - Session before: {dict(session)}")
        
        # Check state parameter manually first
        received_state = request.args.get('state')
        cookie_state = request.cookies.get('oauth_state')
        session_state = session.get('oauth_state')
        
        current_app.logger.info(f"OAuth Callback - Received state: {received_state}")
        current_app.logger.info(f"OAuth Callback - Cookie state: {cookie_state}")
        current_app.logger.info(f"OAuth Callback - Session state (before set): {session_state}")

        # Validate using cookie-based state (reliable across devices)
        if not cookie_state or not received_state or received_state != cookie_state:
            raise Exception("State parameter mismatch. Possible CSRF attack.")
        
        # Clear any old session state and set the validated state
        session.clear()
        session['oauth_state'] = received_state
        session.modified = True
        
        current_app.logger.info(f"OAuth Callback - Session state (after set): {session.get('oauth_state')}")
        
        # Bypass Authlib's state validation by manually fetching the token
        # We've already validated the state securely using cookies
        from authlib.integrations.requests_client import OAuth2Session as AuthlibOAuth2Session
        
        # Create OAuth2 session for token exchange
        client = AuthlibOAuth2Session(
            client_id=oauth.oauth_provider.client_id,
            client_secret=oauth.oauth_provider.client_secret,
            redirect_uri=os.environ.get('OAUTH_REDIRECT_URI'),
            state=received_state
        )
        
        # Exchange authorization code for access token
        token = client.fetch_token(
            url=current_app.config['OAUTH_TOKEN_URL'],
            authorization_response=request.url,
        )
        
        # Fetch user info using the access token
        resp = client.get(current_app.config['OAUTH_USERINFO_URL'])
        user_info = resp.json()
        token['userinfo'] = user_info
        
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
    lang = get_language_from_request()
    
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
        return jsonify({'error': get_message('no_session_id_provided', lang)}), 400
        
    # Get the session from database with row-level lock
    oauth_session = OAuthSession.query.filter_by(id=session_id).with_for_update().first()
    if not oauth_session:
        current_app.logger.debug(f"Invalid session ID requested: {session_id}")
        return jsonify({'error': get_message('invalid_session', lang)}), 401
    
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
                return jsonify({'error': get_message('session_expired_refresh_failed', lang)}), 401
        else:
            return jsonify({'error': get_message('session_expired', lang)}), 401
    
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
    lang = get_language_from_request()
    
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
                'message': get_message('no_session_id_provided', lang)
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
            'message': get_message('successfully_logged_out', lang)
        })
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'message': get_message('logout_error', lang, error=str(e))
        }), 500
