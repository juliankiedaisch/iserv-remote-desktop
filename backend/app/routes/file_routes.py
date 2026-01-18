from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models.oauth_session import OAuthSession
from app.models.desktop_assignments import DesktopAssignment
from app.middlewares.auth import require_auth
from app.i18n import get_message, get_language_from_request
import os
import shutil
from datetime import datetime, timezone

file_bp = Blueprint('file', __name__)


def get_container_path(user_id, space='private'):
    """Get the host path for user's container files"""
    if space == 'public':
        return current_app.config.get('SHARED_PUBLIC_DIR', '/data/shared/public')
    else:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        # User's private files are in PRIVATE subdirectory (shared across containers)
        return os.path.join(user_data_base, str(user_id), 'PRIVATE')


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
@require_auth
def list_files(user_dict):
    """List files in user's private or public space"""
    lang = get_language_from_request()
    
    try:
        oauth_session = request.oauth_session
        user = oauth_session.user
        space = request.args.get('space', 'private')  # 'private' or 'public'
        path = request.args.get('path', '')  # relative path within the space
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        
        # Get user's assignments if they're a teacher to mark shared folders
        teacher_assignments = []
        if user.role == 'teacher' or user.role == 'admin':
            teacher_assignments = DesktopAssignment.query.filter_by(created_by=user.id).all()
        
        # Ensure user directory exists for private space
        if space == 'private':
            from app.utils.directory_manager import ensure_user_directory
            ensure_user_directory(user.id)
        
        full_path = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, full_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': get_message('invalid_path', lang)
            }), 403
        
        # Check if path exists - if base directory doesn't exist, return empty list
        if not os.path.exists(full_path):
            # If it's the base path itself that doesn't exist, return empty list instead of error
            if full_path == base_path:
                return jsonify({
                    'success': True,
                    'items': [],
                    'current_path': path
                })
            return jsonify({
                'success': False,
                'error': get_message('directory_not_found', lang)
            }), 404
        
        # List files and directories
        items = []
        for item_name in os.listdir(full_path):
            # Skip the Public folder in private space at root level
            if space == 'private' and not path and item_name == 'Public':
                continue
            
            item_path = os.path.join(full_path, item_name)
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                rel_item_path = os.path.join(path, item_name) if path else item_name
                
                # Check if this folder is associated with an assignment
                is_shared = False
                assignment_info = None
                if is_dir and space == 'private' and teacher_assignments:
                    for assignment in teacher_assignments:
                        if assignment.assignment_folder_path:
                            # Normalize paths for comparison (remove leading/trailing slashes)
                            assignment_path = assignment.assignment_folder_path.strip('/')
                            item_path = rel_item_path.strip('/')
                            
                            # Check for exact match
                            if assignment_path == item_path:
                                is_shared = True
                                assignment_info = {
                                    'id': assignment.id,
                                    'folder_name': assignment.assignment_folder_name,
                                    'desktop_image_id': assignment.desktop_image_id
                                }
                                break
                
                items.append({
                    'name': item_name,
                    'path': rel_item_path,
                    'is_directory': is_dir,
                    'size': stat.st_size if not is_dir else None,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'is_shared': is_shared,
                    'assignment_info': assignment_info
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
@require_auth
def upload_file(user_dict):
    """Upload a file to user's private or public space"""
    lang = get_language_from_request()
    
    try:
        oauth_session = request.oauth_session
        user = oauth_session.user
        space = request.form.get('space', 'private')
        path = request.form.get('path', '')  # relative path within the space
        
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': get_message('no_file_provided', lang)
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': get_message('no_file_selected', lang)
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        target_dir = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, target_dir)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': get_message('invalid_path', lang)
            }), 403
        
        # Validate that parent directory exists (no implicit directory creation)
        if not os.path.exists(target_dir):
            return jsonify({
                'success': False,
                'error': get_message('upload_directory_not_exist', lang)
            }), 400
        
        # Secure the filename
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({
                'success': False,
                'error': get_message('invalid_filename', lang)
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
            'message': get_message('file_uploaded', lang),
            'filename': filename
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to upload file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/download', methods=['GET'])
@require_auth
def download_file(user_dict):
    """Download a file from user's private or public space"""
    lang = get_language_from_request()
    
    try:
        oauth_session = request.oauth_session
        user = oauth_session.user
        space = request.args.get('space', 'private')
        path = request.args.get('path', '')
        
        if not path:
            return jsonify({
                'success': False,
                'error': get_message('no_file_path_provided', lang)
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        file_path = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, file_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': get_message('invalid_path', lang)
            }), 403
        
        # Check if file exists and is a file
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': get_message('file_not_found', lang)
            }), 404
        
        if not os.path.isfile(file_path):
            return jsonify({
                'success': False,
                'error': get_message('path_not_file', lang)
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
@require_auth
def delete_file(user_dict):
    """Delete a file or directory from user's private or public space"""
    lang = get_language_from_request()
    
    try:
        oauth_session = request.oauth_session
        user = oauth_session.user
        space = request.args.get('space', 'private')
        path = request.args.get('path', '')
        
        if not path:
            return jsonify({
                'success': False,
                'error': get_message('no_file_path_provided', lang)
            }), 400
        
        # Get the base path on host
        base_path = get_container_path(user.id, space)
        target_path = os.path.join(base_path, path.lstrip('/'))
        
        # Security check: ensure path is within base directory
        is_valid, error_msg = validate_path_security(base_path, target_path)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': get_message('invalid_path', lang)
            }), 403
        
        # Don't allow deleting the base directory itself
        if target_path == base_path:
            return jsonify({
                'success': False,
                'error': get_message('cannot_delete_base_directory', lang)
            }), 403
        
        # Check if path exists
        if not os.path.exists(target_path):
            return jsonify({
                'success': False,
                'error': get_message('file_or_directory_not_found', lang)
            }), 404
        
        # Delete the file or directory
        if os.path.isfile(target_path):
            os.remove(target_path)
        else:
            shutil.rmtree(target_path)
        
        return jsonify({
            'success': True,
            'message': get_message('file_deleted', lang)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to delete file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/create-folder', methods=['POST'])
@require_auth
def create_folder(user_dict):
    """Create a new folder in user's private or public space"""
    lang = get_language_from_request()
    
    try:
        oauth_session = request.oauth_session
        user = oauth_session.user
        data = request.get_json() or {}
        space = data.get('space', 'private')
        path = data.get('path', '')  # parent path
        folder_name = data.get('folder_name', '')
        
        if not folder_name:
            return jsonify({
                'success': False,
                'error': get_message('no_folder_name_provided', lang)
            }), 400
        
        # Secure the folder name
        folder_name = secure_filename(folder_name)
        if not folder_name:
            return jsonify({
                'success': False,
                'error': get_message('invalid_folder_name', lang)
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
                'error': get_message('invalid_path', lang)
            }), 403
        
        # Check if folder already exists
        if os.path.exists(new_folder_path):
            return jsonify({
                'success': False,
                'error': get_message('folder_already_exists', lang)
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
            'message': get_message('folder_created', lang),
            'folder_name': folder_name
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to create folder: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@file_bp.route('/files/move', methods=['POST'])
@require_auth
def move_file(user_dict):
    """Move a file or folder to a different location"""
    lang = get_language_from_request()
    
    try:
        oauth_session = request.oauth_session
        user = oauth_session.user
        data = request.get_json() or {}
        space = data.get('space', 'private')
        source_path = data.get('source_path', '')
        destination_path = data.get('destination_path', '')
        
        if not source_path or not destination_path:
            return jsonify({
                'success': False,
                'error': get_message('source_dest_paths_required', lang)
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
                'error': get_message('invalid_path', lang)
            }), 403
        
        is_valid_dest, error_msg = validate_path_security(base_path, full_destination)
        if not is_valid_dest:
            return jsonify({
                'success': False,
                'error': get_message('invalid_path', lang)
            }), 403
        
        # Check if source exists
        if not os.path.exists(full_source):
            return jsonify({
                'success': False,
                'error': get_message('source_not_found', lang)
            }), 404
        
        # Check if destination is a directory
        if not os.path.isdir(full_destination):
            return jsonify({
                'success': False,
                'error': get_message('dest_must_be_directory', lang)
            }), 400
        
        # Get the name of the source file/folder
        source_name = os.path.basename(full_source)
        new_location = os.path.join(full_destination, source_name)
        
        # Security check for new location
        is_valid_new, error_msg = validate_path_security(base_path, new_location)
        if not is_valid_new:
            return jsonify({
                'success': False,
                'error': get_message('invalid_path', lang)
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
                        'error': get_message('cannot_move_into_itself', lang)
                    }), 400
            except (OSError, ValueError) as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 400
        
        # Check if destination already exists
        if os.path.exists(new_location):
            return jsonify({
                'success': False,
                'error': get_message('item_exists_in_dest', lang, name=source_name)
            }), 400
        
        # Calculate the new relative path (relative to base_path)
        new_relative_path = os.path.relpath(new_location, base_path)
        
        # Check if the source is associated with any assignments (for teachers)
        source_relative_path = os.path.relpath(full_source, base_path)
        updated_assignments = []
        
        if os.path.isdir(full_source) and space == 'private':
            # Check if this folder or any parent folder has assignments
            assignments = DesktopAssignment.query.filter_by(created_by=user.id).all()
            for assignment in assignments:
                if assignment.assignment_folder_path:
                    # Check if the assignment path matches or is inside the moved folder
                    if (assignment.assignment_folder_path == source_relative_path or
                        assignment.assignment_folder_path.startswith(source_relative_path + os.sep)):
                        
                        # Calculate the new assignment path
                        # Replace the old prefix with the new one
                        if assignment.assignment_folder_path == source_relative_path:
                            new_assignment_path = new_relative_path
                        else:
                            # For subfolders, preserve the relative structure
                            suffix = assignment.assignment_folder_path[len(source_relative_path):].lstrip(os.sep)
                            new_assignment_path = os.path.join(new_relative_path, suffix)
                        
                        # Update the assignment
                        old_path = assignment.assignment_folder_path
                        assignment.assignment_folder_path = new_assignment_path
                        updated_assignments.append({
                            'id': assignment.id,
                            'old_path': old_path,
                            'new_path': new_assignment_path
                        })
                        current_app.logger.info(f"Updated assignment {assignment.id} path from '{old_path}' to '{new_assignment_path}'")
            
            # Commit assignment updates
            if updated_assignments:
                db.session.commit()
        
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
        
        response = {
            'success': True,
            'message': get_message('moved_successfully', lang) if not updated_assignments else get_message('moved_and_updated_assignments', lang, count=len(updated_assignments))
        }
        
        if updated_assignments:
            response['updated_assignments'] = updated_assignments
        
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Failed to move file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
