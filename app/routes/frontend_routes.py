from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from app.middlewares.auth import require_session
from app.models.oauth_session import OAuthSession
from app.models.containers import Container
from app.models.users import User
from app import db

frontend_bp = Blueprint('frontend', __name__)

@frontend_bp.route('/')
def index():
    """Main frontend page - desktop selection"""
    # Check if user has session_id in query params
    session_id = request.args.get('session_id')
    
    if not session_id:
        # Check if user might have it in localStorage (will be checked by JS)
        # For now, just render the page - JS will handle auth
        pass
    
    # Check if user is admin (if session_id provided)
    is_admin = False
    if session_id:
        oauth_session = OAuthSession.query.filter_by(id=session_id).first()
        if oauth_session and oauth_session.user:
            is_admin = oauth_session.user.is_admin
    
    return render_template('index.html', is_admin=is_admin)


@frontend_bp.route('/admin')
def admin_panel():
    """Admin panel page"""
    return render_template('admin.html')
