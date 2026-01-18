from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.users import User
from app.models.oauth_session import OAuthSession
from app.models.desktop_assignments import DesktopImage
from app.services.docker_manager import DockerManager
from app.middlewares.auth import require_auth
from app.i18n import get_message, get_language_from_request
from datetime import datetime, timezone
import os

config_bp = Blueprint('config', __name__)


@config_bp.route('/config/reset', methods=['POST'])
@require_auth
def reset_config(user_dict):
    """
    Reset user's config for a specific image to default template.
    
    Request body:
        {
            "image_name": "teacherki/kasm-desktop:latest"
        }
    """
    lang = get_language_from_request()
    oauth_session = request.oauth_session
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
@require_auth
def refresh_template(user_dict):
    """
    Refresh config template from an image (admin only).
    
    Request body:
        {
            "image_name": "teacherki/kasm-desktop:latest"
        }
    """
    lang = get_language_from_request()
    oauth_session = request.oauth_session
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
@require_auth
def list_configs(user_dict):
    """
    List all config directories for the current user.
    """
    lang = get_language_from_request()
    oauth_session = request.oauth_session
    user = oauth_session.user
    
    try:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        template_data_base = current_app.config.get('TEMPLATE_DATA_BASE_DIR', '/data/templates')
        user_base_dir = os.path.join(user_data_base, str(user.id))
        
        if not os.path.exists(user_base_dir):
            return jsonify({
                'success': True,
                'configs': []
            })
        
        configs = []
        # Iterate through user directory to find desktop-type config directories
        # Skip special directories like PRIVATE
        skip_dirs = {'PRIVATE', 'configs', 'config_templates', 'files'}
        
        for item_name in os.listdir(user_base_dir):
            item_path = os.path.join(user_base_dir, item_name)
            # Check if it's a directory and not in skip list
            if os.path.isdir(item_path) and item_name not in skip_dirs:
                # Try to find matching desktop image by name
                desktop_image = DesktopImage.query.filter_by(name=item_name).first()
                
                # If found, check for template
                if desktop_image:
                    image_dir_name = desktop_image.docker_image.replace('/', '-').replace(':', '-')
                    centralized_template = os.path.join(template_data_base, image_dir_name)
                    
                    config_info = {
                        'desktop_type': item_name,
                        'image_name': desktop_image.docker_image,
                        'display_name': desktop_image.name,
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
def get_config_info(user_dict, image_dir):
    """
    Get detailed information about a specific config.
    """
    lang = get_language_from_request()
    oauth_session = request.oauth_session
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
