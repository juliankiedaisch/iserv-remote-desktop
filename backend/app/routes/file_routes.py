from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models.oauth_session import OAuthSession
from functools import wraps
import os
import shutil
from datetime import datetime, timezone

file_bp = Blueprint('file', __name__)

def require_session(f):
    """Decorator to require valid session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get session ID from various sources
        session_id = request.args.get('session_id')
        
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header.split(' ')[1]
        
        if not session_id:
            return jsonify({'error': 'No session ID provided'}), 400
        
        # Validate session
        oauth_session = OAuthSession.query.filter_by(id=session_id).first()
        if not oauth_session:
            return jsonify({'error': 'Invalid session'}), 401
        
        # Check if session is expired
        current_time = datetime.now(timezone.utc)
        expires_at = oauth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < current_time:
            return jsonify({'error': 'Session expired'}), 401
        
        # Update last accessed
        oauth_session.last_accessed = current_time
        db.session.commit()
        
        # Pass session to the route
        return f(oauth_session, *args, **kwargs)
    
    return decorated_function


def get_container_path(user_id, space='private'):
    """Get the host path for user's container files"""
    if space == 'public':
        return current_app.config.get('SHARED_PUBLIC_DIR', '/data/shared/public')
    else:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        return os.path.join(user_data_base, str(user_id))


def validate_path_security(base_path, full_path):
    """
    Validate that the full path is within the base directory.
    
    Args:
        base_path: The allowed base directory path
        full_path: The path to validate
        
    Returns:
        tuple: (is_valid, error_message) - is_valid is True if path is safe
    """
    try:
        # Resolve to canonical paths to prevent traversal attacks
        full_path = os.path.realpath(full_path)
        base_path = os.path.realpath(base_path)
        
        # Check if path is within base directory
        # Use os.sep to handle both exact match and subdirectories
        if full_path == base_path or full_path.startswith(base_path + os.sep):
            return True, None
        
        return False, 'Invalid path: outside allowed directory'
    except (OSError, ValueError) as e:
        return False, f'Invalid path: {str(e)}'


@file_bp.route('/files/list', methods=['GET'])
@require_session
def list_files(oauth_session):
    """List files in user's private or public space"""
    try:
        user = oauth_session.user
        space = request.args.get('space', 'private')  # 'private' or 'public'
        path = request.args.get('path', '')  # relative path within the space
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        full_path = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, full_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
        
        # Check if path exists
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'error': 'Directory not found'
            }), 404
        
        # List files and directories
        items = []
        for item_name in os.listdir(full_path):
            item_path = os.path.join(full_path, item_name)
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                items.append({
                    'name': item_name,
                    'path': os.path.join(path, item_name) if path else item_name,
                    'is_directory': is_dir,
                    'size': stat.st_size if not is_dir else None,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception as e:
                current_app.logger.warning(f"Could not stat file {item_name}: {str(e)}")
                continue
        
        # Sort: directories first, then files, alphabetically
        items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
        
        return jsonify({
            'success': True,
            'items': items,
            'current_path': path
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to list files: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/upload', methods=['POST'])
@require_session
def upload_file(oauth_session):
    """Upload a file to user's private or public space"""
    try:
        user = oauth_session.user
        space = request.form.get('space', 'private')
        path = request.form.get('path', '')  # relative path within the space
        
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        target_dir = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, target_dir)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
        
        # Validate that parent directory exists (no implicit directory creation)
        if not os.path.exists(target_dir):
            return jsonify({
                'success': False,
                'error': 'Upload directory does not exist. Please create it first.'
            }), 400
        
        # Secure the filename
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({
                'success': False,
                'error': 'Invalid filename'
            }), 400
        
        # Save the file
        file_path = os.path.join(target_dir, filename)
        file.save(file_path)
        
        # Set proper permissions
        try:
            uid = current_app.config.get('CONTAINER_USER_ID', 1000)
            gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
            os.chown(file_path, uid, gid)
            os.chmod(file_path, 0o644)
        except Exception as e:
            current_app.logger.warning(f"Could not set ownership/permissions: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'filename': filename
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to upload file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/download', methods=['GET'])
@require_session
def download_file(oauth_session):
    """Download a file from user's private or public space"""
    try:
        user = oauth_session.user
        space = request.args.get('space', 'private')
        path = request.args.get('path', '')
        
        if not path:
            return jsonify({
                'success': False,
                'error': 'No file path provided'
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        file_path = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, file_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
        
        # Check if file exists and is a file
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        if not os.path.isfile(file_path):
            return jsonify({
                'success': False,
                'error': 'Path is not a file'
            }), 400
        
        # Send the file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to download file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/delete', methods=['DELETE'])
@require_session
def delete_file(oauth_session):
    """Delete a file or directory from user's private or public space"""
    try:
        user = oauth_session.user
        space = request.args.get('space', 'private')
        path = request.args.get('path', '')
        
        if not path:
            return jsonify({
                'success': False,
                'error': 'No file path provided'
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        target_path = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, target_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
        
        # Don't allow deleting the base directory itself
        if target_path == base_path:
            return jsonify({
                'success': False,
                'error': 'Cannot delete base directory'
            }), 403
        
        # Check if path exists
        if not os.path.exists(target_path):
            return jsonify({
                'success': False,
                'error': 'File or directory not found'
            }), 404
        
        # Delete the file or directory
        if os.path.isfile(target_path):
            os.remove(target_path)
        else:
            shutil.rmtree(target_path)
        
        return jsonify({
            'success': True,
            'message': 'Deleted successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to delete file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/create-folder', methods=['POST'])
@require_session
def create_folder(oauth_session):
    """Create a new folder in user's private or public space"""
    try:
        user = oauth_session.user
        data = request.get_json() or {}
        space = data.get('space', 'private')
        path = data.get('path', '')  # parent path
        folder_name = data.get('folder_name', '')
        
        if not folder_name:
            return jsonify({
                'success': False,
                'error': 'No folder name provided'
            }), 400
        
        # Secure the folder name
        folder_name = secure_filename(folder_name)
        if not folder_name:
            return jsonify({
                'success': False,
                'error': 'Invalid folder name'
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        parent_dir = os.path.join(base_path, path.lstrip('/'))
        new_folder_path = os.path.join(parent_dir, folder_name)
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, new_folder_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
        
        # Check if folder already exists
        if os.path.exists(new_folder_path):
            return jsonify({
                'success': False,
                'error': 'Folder already exists'
            }), 400
        
        # Create the folder
        os.makedirs(new_folder_path, exist_ok=True)
        
        # Set proper permissions
        try:
            uid = current_app.config.get('CONTAINER_USER_ID', 1000)
            gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
            os.chown(new_folder_path, uid, gid)
            os.chmod(new_folder_path, 0o755)
        except Exception as e:
            current_app.logger.warning(f"Could not set ownership/permissions: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Folder created successfully',
            'folder_name': folder_name
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to create folder: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/move', methods=['POST'])
@require_session
def move_file(oauth_session):
    """Move a file or folder to a different location"""
    try:
        user = oauth_session.user
        data = request.get_json() or {}
        space = data.get('space', 'private')
        source_path = data.get('source_path', '')
        destination_path = data.get('destination_path', '')
        
        if not source_path or not destination_path:
            return jsonify({
                'success': False,
                'error': 'Source and destination paths are required'
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        
        # Build full paths
        full_source = os.path.join(base_path, source_path.lstrip('/'))
        full_destination = os.path.join(base_path, destination_path.lstrip('/'))
        
        # Security check: ensure both paths are within base directory
        is_valid_source, error_msg = validate_path_security(base_path, full_source)
        if not is_valid_source:
            return jsonify({
                'success': False,
                'error': f'Invalid source path: {error_msg}'
            }), 403
        
        is_valid_dest, error_msg = validate_path_security(base_path, full_destination)
        if not is_valid_dest:
            return jsonify({
                'success': False,
                'error': f'Invalid destination path: {error_msg}'
            }), 403
        
        # Check if source exists
        if not os.path.exists(full_source):
            return jsonify({
                'success': False,
                'error': 'Source file or directory not found'
            }), 404
        
        # Check if destination is a directory
        if not os.path.isdir(full_destination):
            return jsonify({
                'success': False,
                'error': 'Destination must be a directory'
            }), 400
        
        # Get the name of the source file/folder
        source_name = os.path.basename(full_source)
        new_location = os.path.join(full_destination, source_name)
        
        # Security check for new location
        is_valid_new, error_msg = validate_path_security(base_path, new_location)
        if not is_valid_new:
            return jsonify({
                'success': False,
                'error': f'Invalid new location: {error_msg}'
            }), 403
        
        # Check if trying to move into itself (for directories)
        if os.path.isdir(full_source):
            try:
                # Normalize paths to handle trailing slashes
                source_real = os.path.realpath(full_source)
                dest_real = os.path.realpath(full_destination)
                
                # Check if destination is inside source
                if dest_real.startswith(source_real + os.sep) or dest_real == source_real:
                    return jsonify({
                        'success': False,
                        'error': 'Cannot move a folder into itself'
                    }), 400
            except (OSError, ValueError) as e:
                return jsonify({
                    'success': False,
                    'error': f'Path validation error: {str(e)}'
                }), 400
        
        # Check if destination already exists
        if os.path.exists(new_location):
            return jsonify({
                'success': False,
                'error': f'A file or folder named "{source_name}" already exists in the destination'
            }), 400
        
        # Move the file or directory
        shutil.move(full_source, new_location)
        
        # Set proper permissions
        try:
            uid = current_app.config.get('CONTAINER_USER_ID', 1000)
            gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
            os.chown(new_location, uid, gid)
            if os.path.isdir(new_location):
                # Recursively set permissions for directories
                for root, dirs, files in os.walk(new_location):
                    os.chown(root, uid, gid)
                    os.chmod(root, 0o755)
                    for file in files:
                        file_path = os.path.join(root, file)
                        os.chown(file_path, uid, gid)
                        os.chmod(file_path, 0o644)
            else:
                os.chmod(new_location, 0o644)
        except Exception as e:
            current_app.logger.warning(f"Could not set ownership/permissions: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Moved successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to move file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
