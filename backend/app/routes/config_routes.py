from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.users import User
from app.models.desktop_assignments import DesktopImage
from app.services.docker_manager import DockerManager
from functools import wraps
from app.i18n import get_message, get_language_from_request
import os

config_bp = Blueprint('config', __name__)


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get user from session or token
        # For now, use a simple implementation
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return f(user, *args, **kwargs)
    
    return decorated_function


@config_bp.route('/config/reset', methods=['POST'])
@require_auth
def reset_config(user):
    """
    Reset user's config for a specific image to default template.
    
    Request body:
        {
            "image_name": "teacherki/kasm-desktop:latest"
        }
    """
    lang = get_language_from_request()
    
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
@require_auth
def refresh_template(user):
    """
    Refresh config template from an image (admin only).
    
    Request body:
        {
            "image_name": "teacherki/kasm-desktop:latest"
        }
    """
    lang = get_language_from_request()
    
    try:
        # Check if user is admin
        if user.role != 'admin':
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
@require_auth
def list_configs(user):
    """
    List all config directories for the current user.
    """
    lang = get_language_from_request()
    
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
@require_auth
def get_config_info(user, image_dir):
    """
    Get detailed information about a specific config.
    """
    lang = get_language_from_request()
    
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
