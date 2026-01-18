from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.users import User
from app.models.oauth_session import OAuthSession
from app.models.desktop_assignments import DesktopImage
from app.services.docker_manager import DockerManager
from functools import wraps
from app.i18n import get_message, get_language_from_request
from datetime import datetime, timezone
import os

config_bp = Blueprint('config', __name__)


def require_session(f):
    """Decorator to require valid session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        lang = get_language_from_request()
        
        # Get session ID from various sources
        session_id = request.args.get('session_id')
        
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            return jsonify({'error': get_message('no_session_id_provided', lang)}), 400
        
        # Validate session
        oauth_session = OAuthSession.query.filter_by(id=session_id).first()
        if not oauth_session:
            return jsonify({'error': get_message('invalid_session', lang)}), 401
        
        # Check if session is expired
        current_time = datetime.now(timezone.utc)
        expires_at = oauth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < current_time:
            return jsonify({'error': get_message('session_expired', lang)}), 401
        
        # Update last accessed
        oauth_session.last_accessed = current_time
        db.session.commit()
        
        # Pass session to the route
        return f(oauth_session, *args, **kwargs)
    
    return decorated_function


@config_bp.route('/config/reset', methods=['POST'])
@require_session
def reset_config(oauth_session):
    """
    Reset user's config for a specific image to default template.
    
    Request body:
        {
            "image_name": "teacherki/kasm-desktop:latest"
        }
    """
    lang = get_language_from_request()
    user = oauth_session.user
    
    try:
        data = request.get_json() or {}
        image_name = data.get('image_name')
        
        if not image_name:
            return jsonify({
                'success': False,
                'error': get_message('no_image_name_provided', lang)
            }), 400
        
        # Verify image exists
        desktop_image = DesktopImage.query.filter_by(docker_image=image_name).first()
        if not desktop_image:
            return jsonify({
                'success': False,
                'error': get_message('desktop_image_not_found', lang)
            }), 404
        
        # Reset config
        docker_manager = DockerManager()
        result = docker_manager.reset_user_config(user.id, image_name)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.error(f"Failed to reset config: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/config/templates/refresh', methods=['POST'])
@require_session
def refresh_template(oauth_session):
    """
    Refresh config template from an image (admin only).
    
    Request body:
        {
            "image_name": "teacherki/kasm-desktop:latest"
        }
    """
    lang = get_language_from_request()
    user = oauth_session.user
    
    try:
        # Check if user is admin
        if not user.is_admin:
            return jsonify({
                'success': False,
                'error': get_message('admin_required', lang)
            }), 403
        
        data = request.get_json() or {}
        image_name = data.get('image_name')
        
        if not image_name:
            return jsonify({
                'success': False,
                'error': get_message('no_image_name_provided', lang)
            }), 400
        
        # Refresh template
        docker_manager = DockerManager()
        result = docker_manager.refresh_config_template(image_name)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.error(f"Failed to refresh template: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/config/list', methods=['GET'])
@require_session
def list_configs(oauth_session):
    """
    List all config directories for the current user.
    """
    lang = get_language_from_request()
    user = oauth_session.user
    
    try:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        template_data_base = current_app.config.get('TEMPLATE_DATA_BASE_DIR', '/data/templates')
        configs_base = os.path.join(user_data_base, str(user.id), 'configs')
        
        if not os.path.exists(configs_base):
            return jsonify({
                'success': True,
                'configs': []
            })
        
        configs = []
        for image_dir in os.listdir(configs_base):
            config_path = os.path.join(configs_base, image_dir)
            if os.path.isdir(config_path):
                # Try to find matching desktop image
                image_name = image_dir.replace('-', '/', 1).replace('-', ':', 1)
                desktop_image = DesktopImage.query.filter_by(docker_image=image_name).first()
                
                # Check centralized template location
                centralized_template = os.path.join(template_data_base, image_dir)
                
                # Get config info
                config_info = {
                    'image_dir': image_dir,
                    'image_name': image_name if desktop_image else None,
                    'display_name': desktop_image.name if desktop_image else image_dir,
                    'has_template': os.path.exists(centralized_template)
                }
                configs.append(config_info)
        
        return jsonify({
            'success': True,
            'configs': configs
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to list configs: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/config/info/<image_dir>', methods=['GET'])
@require_session
def get_config_info(oauth_session, image_dir):
    """
    Get detailed information about a specific config.
    """
    lang = get_language_from_request()
    user = oauth_session.user
    
    try:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        template_data_base = current_app.config.get('TEMPLATE_DATA_BASE_DIR', '/data/templates')
        config_path = os.path.join(user_data_base, str(user.id), 'configs', image_dir)
        template_path = os.path.join(template_data_base, image_dir)
        
        if not os.path.exists(config_path):
            return jsonify({
                'success': False,
                'error': get_message('config_not_found', lang)
            }), 404
        
        # Get directory info
        import os.path
        from datetime import datetime
        
        stat = os.stat(config_path)
        
        info = {
            'image_dir': image_dir,
            'config_path': config_path,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'has_template': os.path.exists(template_path),
            'template_path': template_path if os.path.exists(template_path) else None,
            'template_location': 'centralized'
        }
        
        return jsonify({
            'success': True,
            'info': info
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get config info: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
