"""
Directory management utilities for creating and maintaining data directories
"""
import os
from flask import current_app


def ensure_directory_exists(path, uid=None, gid=None):
    """
    Create directory if it doesn't exist and set ownership
    
    Args:
        path: Directory path to create
        uid: User ID to set as owner (optional)
        gid: Group ID to set as owner (optional)
    """
    try:
        os.makedirs(path, exist_ok=True)
        
        if uid is not None and gid is not None:
            try:
                os.chown(path, uid, gid)
                current_app.logger.info(f"Created directory {path} with ownership {uid}:{gid}")
            except Exception as e:
                current_app.logger.warning(f"Could not set ownership on {path}: {str(e)}")
        else:
            current_app.logger.info(f"Created directory {path}")
            
    except Exception as e:
        current_app.logger.error(f"Failed to create directory {path}: {str(e)}")
        raise


def initialize_base_directories():
    """
    Initialize base data directories on application startup
    Creates the shared public directory and user data base directory
    """
    try:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        shared_public = current_app.config.get('SHARED_PUBLIC_DIR', '/data/shared/public')
        container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
        container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
        
        # Create base user data directory
        ensure_directory_exists(user_data_base, container_uid, container_gid)
        
        # Create shared public directory
        ensure_directory_exists(shared_public, container_uid, container_gid)
        
        current_app.logger.info("Base directories initialized successfully")
        
    except Exception as e:
        current_app.logger.error(f"Failed to initialize base directories: {str(e)}")
        # Don't raise - allow app to continue even if directory creation fails
        # This allows for graceful degradation


def ensure_user_directory(user_id):
    """
    Ensure a user's data directory exists
    Called when a user logs in or creates a container
    
    Args:
        user_id: User's unique ID
        
    Returns:
        str: Path to the user's data directory
    """
    try:
        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
        container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
        container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
        
        user_dir = os.path.join(user_data_base, str(user_id))
        ensure_directory_exists(user_dir, container_uid, container_gid)
        
        return user_dir
        
    except Exception as e:
        current_app.logger.error(f"Failed to ensure user directory for {user_id}: {str(e)}")
        raise
