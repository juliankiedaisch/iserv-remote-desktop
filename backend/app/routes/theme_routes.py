from flask import Blueprint, jsonify, request
from app import db
from app.models.theme_settings import ThemeSettings
from app.middlewares.auth import require_auth, require_admin
import json
import base64
import os

theme_routes = Blueprint('theme', __name__)


@theme_routes.route('/api/theme', methods=['GET'])
def get_theme():
    """Get current theme settings."""
    try:
        theme = ThemeSettings.get_current_theme()
        return jsonify({
            'success': True,
            'theme': theme.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@theme_routes.route('/api/theme', methods=['PUT'])
@require_auth
@require_admin
def update_theme():
    """Update theme settings (admin only)."""
    try:
        data = request.get_json()
        
        if not data or 'settings' not in data:
            return jsonify({
                'success': False,
                'error': 'Theme settings are required'
            }), 400
        
        theme = ThemeSettings.get_current_theme()
        theme.theme_dict = data['settings']
        
        if 'favicon' in data:
            theme.favicon = data['favicon']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'theme': theme.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@theme_routes.route('/api/theme/export', methods=['GET'])
@require_auth
@require_admin
def export_theme():
    """Export theme as JSON file (admin only)."""
    try:
        theme = ThemeSettings.get_current_theme()
        return jsonify({
            'success': True,
            'theme': {
                'settings': theme.theme_dict,
                'favicon': theme.favicon
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@theme_routes.route('/api/theme/import', methods=['POST'])
@require_auth
@require_admin
def import_theme():
    """Import theme from JSON data (admin only)."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Theme data is required'
            }), 400
        
        theme = ThemeSettings.get_current_theme()
        
        if 'settings' in data:
            theme.theme_dict = data['settings']
        
        if 'favicon' in data:
            theme.favicon = data['favicon']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'theme': theme.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@theme_routes.route('/api/theme/reset', methods=['POST'])
@require_auth
@require_admin
def reset_theme():
    """Reset theme to default settings (admin only)."""
    try:
        theme = ThemeSettings.get_current_theme()
        
        default_theme = {
            'color-primary': '#3e59d1',
            'color-primary-dark': '#303383',
            'color-primary-gradient-start': '#667eea',
            'color-primary-gradient-end': '#764ba2',
            'color-secondary': '#38d352',
            'color-secondary-dark': '#278d31',
            'color-success': '#28a745',
            'color-danger': '#dc3545',
            'color-danger-hover': '#c82333',
            'color-warning': '#ffc107',
            'color-info': '#17a2b8',
            'color-gray': '#6c757d',
            'color-gray-dark': '#5a6268',
            'color-admin-badge': '#aaffad',
            'color-admin-button': '#32469c',
            'color-admin-button-hover': '#2d3c8d',
        }
        
        theme.theme_dict = default_theme
        theme.favicon = None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'theme': theme.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@theme_routes.route('/api/theme/favicon', methods=['POST'])
@require_auth
@require_admin
def upload_favicon():
    """Upload a new favicon (admin only)."""
    try:
        data = request.get_json()
        
        if not data or 'favicon' not in data:
            return jsonify({
                'success': False,
                'error': 'Favicon data is required'
            }), 400
        
        theme = ThemeSettings.get_current_theme()
        theme.favicon = data['favicon']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'favicon': theme.favicon
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
