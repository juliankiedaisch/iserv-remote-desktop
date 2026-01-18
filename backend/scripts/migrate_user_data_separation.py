#!/usr/bin/env python3
"""
Migration script to separate user files from container configs.

This script:
1. Creates the new directory structure (files/, configs/, config_templates/)
2. Moves user data to files/
3. Moves config files to configs/default/
4. Preserves permissions and ownership
"""

import os
import shutil
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from app import create_app

# Config patterns (hidden files/dirs that should go to configs/)
CONFIG_PATTERNS = [
    '.config', '.cache', '.local', '.mozilla', '.pki', '.vnc',
    '.bashrc', '.bash_profile', '.profile', '.Xauthority', '.ICEauthority',
    '.gtkrc-2.0', '.kasmpasswd', '.wget-hsts', '.gnupg', '.ssh',
    '.java', '.filius', '.vscode', '.launchpadlib', '.gvfs'
]

# User file directories (visible folders that should go to files/)
USER_FILE_DIRS = [
    'Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 
    'Videos', 'Public', 'PDF', 'Templates'
]


def migrate_user_directory(user_id, user_data_base, default_image='teacherki-kasm-desktop-latest'):
    """
    Migrate a single user's directory from old to new structure.
    
    Args:
        user_id: User ID (directory name)
        user_data_base: Base path for user data
        default_image: Default image name for configs
    """
    user_dir = os.path.join(user_data_base, str(user_id))
    
    # Check if already migrated
    files_dir = os.path.join(user_dir, 'files')
    configs_dir = os.path.join(user_dir, 'configs')
    
    if os.path.exists(files_dir) or os.path.exists(configs_dir):
        print(f"User {user_id} already migrated, skipping...")
        return True
    
    print(f"\nMigrating user {user_id}...")
    
    try:
        # Create new directory structure
        files_path = os.path.join(user_dir, 'files')
        configs_path = os.path.join(user_dir, 'configs', default_image)
        templates_path = os.path.join(user_dir, 'config_templates', default_image)
        
        os.makedirs(files_path, exist_ok=True)
        os.makedirs(configs_path, exist_ok=True)
        os.makedirs(templates_path, exist_ok=True)
        
        # Get UID/GID for proper ownership
        container_uid = 1000
        container_gid = 1000
        
        # Set ownership on new directories
        for dir_path in [files_path, configs_path, templates_path]:
            os.chown(dir_path, container_uid, container_gid)
            os.chmod(dir_path, 0o755)
        
        # List all items in user directory
        items = []
        try:
            items = os.listdir(user_dir)
        except PermissionError:
            print(f"  WARNING: Permission denied reading {user_dir}")
            return False
        
        moved_files = 0
        moved_configs = 0
        
        for item in items:
            # Skip the new directories we just created
            if item in ['files', 'configs', 'config_templates']:
                continue
            
            source = os.path.join(user_dir, item)
            
            # Determine if it's a config or user file
            is_config = False
            for pattern in CONFIG_PATTERNS:
                if item.startswith(pattern) or item == pattern:
                    is_config = True
                    break
            
            try:
                if is_config:
                    # Move to configs directory
                    dest = os.path.join(configs_path, item)
                    print(f"  Moving config: {item} -> configs/{default_image}/")
                    shutil.move(source, dest)
                    moved_configs += 1
                else:
                    # Move to files directory
                    dest = os.path.join(files_path, item)
                    print(f"  Moving file/dir: {item} -> files/")
                    shutil.move(source, dest)
                    moved_files += 1
            except Exception as e:
                print(f"  ERROR moving {item}: {str(e)}")
                continue
        
        # Ensure standard directories exist in files
        for dir_name in USER_FILE_DIRS:
            dir_path = os.path.join(files_path, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                os.chown(dir_path, container_uid, container_gid)
                os.chmod(dir_path, 0o755)
        
        print(f"  Migrated {moved_files} file items and {moved_configs} config items")
        print(f"  ✓ User {user_id} migration complete")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to migrate user {user_id}: {str(e)}")
        return False


def main():
    """Main migration function"""
    print("=" * 60)
    print("User Data Separation Migration")
    print("=" * 60)
    
    # Create Flask app to get config
    app = create_app()
    
    with app.app_context():
        user_data_base = app.config.get('USER_DATA_BASE_DIR', '/data/users')
        
        print(f"\nUser data base directory: {user_data_base}")
        
        if not os.path.exists(user_data_base):
            print(f"ERROR: User data directory does not exist: {user_data_base}")
            return 1
        
        # Get list of user directories
        try:
            user_dirs = [d for d in os.listdir(user_data_base) 
                        if os.path.isdir(os.path.join(user_data_base, d))]
        except PermissionError:
            print(f"ERROR: Permission denied accessing {user_data_base}")
            return 1
        
        if not user_dirs:
            print("No user directories found.")
            return 0
        
        print(f"Found {len(user_dirs)} user directories to migrate")
        
        # Ask for confirmation
        response = input("\nProceed with migration? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Migration cancelled.")
            return 0
        
        # Migrate each user
        success_count = 0
        fail_count = 0
        
        for user_id in user_dirs:
            if migrate_user_directory(user_id, user_data_base):
                success_count += 1
            else:
                fail_count += 1
        
        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"Total users: {len(user_dirs)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {fail_count}")
        print("=" * 60)
        
        if fail_count > 0:
            print("\nWARNING: Some migrations failed. Check the output above for details.")
            return 1
        
        print("\n✓ All migrations completed successfully!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
