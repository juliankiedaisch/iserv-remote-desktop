import docker
from docker.errors import DockerException, NotFound, APIError
from flask import current_app
import os
import random
import socket
import secrets
from datetime import datetime, timezone
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.containers import Container
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.users import User
import tarfile
import io
import shutil
# Import WebSocket event emitters (lazy import to avoid circular dependencies)
def _emit_container_created(container, user_id):
    try:
        from app.routes.websocket_routes import emit_container_created
        emit_container_created(container, user_id)
    except Exception as e:
        current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")

def _emit_container_status(container, user_id):
    try:
        from app.routes.websocket_routes import emit_container_status
        emit_container_status(container, user_id)
    except Exception as e:
        current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")

def _emit_container_stopped(container, user_id):
    try:
        from app.routes.websocket_routes import emit_container_stopped
        emit_container_stopped(container, user_id)
    except Exception as e:
        current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")

class DockerManager:
    """Manage Docker containers for Kasm workspaces"""
    
    def __init__(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
        except DockerException as e:
            current_app.logger.error(f"Failed to connect to Docker: {str(e)}")
            raise
    
    def create_container(self, user_id, session_id, username, desktop_type=None, desktop_image_id=None, max_retries=3):
        """
        Create and start a Kasm workspace container for a user
        
        Args:
            user_id: User's unique ID
            session_id: Session ID
            username: User's username
            desktop_type: Type of desktop to create (name from desktop_types table)
            desktop_image_id: ID of the desktop image (for access control)
            max_retries: Maximum number of retries on port conflicts (default: 3)
            
        Returns:
            Container model instance
        """
        # Retry logic for race conditions (port conflicts, etc.)
        last_error = None
        for attempt in range(max_retries):
            try:
                return self._create_container_internal(user_id, session_id, username, desktop_type, desktop_image_id)
            except APIError as e:
                error_msg = str(e)
                if 'port is already allocated' in error_msg or 'address already in use' in error_msg:
                    last_error = e
                    current_app.logger.warning(
                        f"Port conflict on attempt {attempt + 1}/{max_retries}: {error_msg}"
                    )
                    if attempt < max_retries - 1:
                        # Small delay before retry to reduce contention
                        import time
                        time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                        continue
                raise  # Re-raise if not a port conflict
            except Exception as e:
                # For other exceptions, don't retry
                raise
        
        # If we exhausted all retries, raise the last error
        raise last_error if last_error else Exception("Failed to create container after retries")
    
    def _create_container_internal(self, user_id, session_id, username, desktop_type=None, desktop_image_id=None):
        """
        Internal method to create container (called by create_container with retry logic)
        """
        container_record = None
        try:
            # Get desktop type from database
            if desktop_type:
                desktop_type_record = DesktopImage.query.filter_by(name=desktop_type, enabled=True).first()
                if not desktop_type_record:
                    raise Exception(f"Desktop type '{desktop_type}' not found or disabled")
                
                kasm_image = desktop_type_record.docker_image
                # Use provided desktop_image_id or get from record
                if not desktop_image_id:
                    desktop_image_id = desktop_type_record.id
            else:
                # Fallback to default if no type specified
                default_type = DesktopImage.query.filter_by(enabled=True).first()
                if default_type:
                    kasm_image = default_type.docker_image
                    desktop_type = default_type.name
                else:
                    # Last resort fallback to environment or hardcoded default
                    kasm_image = os.environ.get('KASM_IMAGE', 'kasmweb/ubuntu-noble-desktop:1.18.0')
                    desktop_type = 'ubuntu-desktop'
            
            container_port = int(os.environ.get('KASM_CONTAINER_PORT', 6901))
            
            # Generate unique container name with desktop type
            container_name = f"kasm-{username}-{desktop_type}-{session_id[:8]}"
            
            # Generate unique proxy path for reverse proxy access with security token
            # Include a random token to prevent unauthorized access by guessing URLs
            # Replace periods with dashes for DNS subdomain compatibility
            username_safe = username.replace('.', '-')
            # Generate URL-safe random token (12 bytes = 16 characters base64url)
            access_token = secrets.token_urlsafe(12)
            proxy_path = f"{username_safe}-{desktop_type}-{access_token}"
            
            # Check if container already exists for this user and desktop type (regardless of session)
            # We want only ONE container per user per desktop_type
            # Use row-level locking to prevent concurrent creation attempts
            existing = Container.query.filter_by(
                user_id=user_id,
                desktop_type=desktop_type
            ).with_for_update(skip_locked=False).first()
            
            if existing:
                # If it's running, update session_id and return it
                if existing.status == 'running':
                    current_app.logger.info(f"Container already exists for user {user_id} and type {desktop_type}")
                    # Update the session_id to the current session
                    existing.session_id = session_id
                    existing.last_accessed = datetime.now(timezone.utc)
                    db.session.commit()
                    return existing
                
                # If stopped, try to restart the existing Docker container
                if existing.status == 'stopped' and existing.container_id:
                    current_app.logger.info(
                        f"Found stopped container {existing.container_name}, attempting to restart"
                    )
                    try:
                        container = self.client.containers.get(existing.container_id)
                        # Restart the existing container
                        container.start()
                        
                        # Update database record with new session
                        existing.session_id = session_id
                        existing.status = 'running'
                        existing.started_at = datetime.now(timezone.utc)
                        existing.last_accessed = datetime.now(timezone.utc)
                        db.session.commit()
                        
                        current_app.logger.info(
                            f"Restarted existing container {existing.container_name} "
                            f"(proxy_path: {existing.proxy_path}, container_id: {existing.container_id})"
                        )
                        
                        # Emit WebSocket event for real-time updates
                        _emit_container_created(existing, user_id)
                        
                        return existing
                    except NotFound:
                        current_app.logger.info(f"Docker container {existing.container_id} not found, will create new")
                        # Container doesn't exist in Docker, clean up DB record and continue to create new
                        db.session.delete(existing)
                        db.session.commit()
                    except Exception as e:
                        current_app.logger.warning(f"Failed to restart container: {str(e)}, will create new")
                        # If restart fails, clean up and create new
                        try:
                            container = self.client.containers.get(existing.container_id)
                            container.remove(force=True)
                        except:
                            pass
                        db.session.delete(existing)
                        db.session.commit()
                
                # If in error or creating state (stuck), clean it up
                if existing.status in ['error', 'creating']:
                    current_app.logger.info(
                        f"Found existing container {existing.container_name} in state {existing.status}, cleaning up"
                    )
                    # Try to remove the Docker container if it exists
                    if existing.container_id:
                        try:
                            container = self.client.containers.get(existing.container_id)
                            container.remove(force=True)
                            current_app.logger.info(f"Removed existing Docker container {existing.container_id}")
                        except NotFound:
                            current_app.logger.info(f"Docker container {existing.container_id} not found")
                        except Exception as e:
                            current_app.logger.warning(f"Failed to remove Docker container: {str(e)}")
                    
                    # Remove the database record
                    db.session.delete(existing)
                    db.session.commit()
                    current_app.logger.info(f"Removed database record for container {existing.container_name}")
            
            # Also check for any containers with conflicting container_name
            # These could be from previous sessions that weren't properly cleaned up
            # Use row-level locking to prevent concurrent cleanup attempts
            # Note: proxy_path now includes random token, so no need to check for conflicts there
            conflicting_containers = Container.query.filter(
                Container.container_name == container_name,
                Container.user_id == user_id  # Only cleanup user's own containers
            ).with_for_update(skip_locked=True).all()
            
            # Track which container IDs we've already cleaned up to avoid duplicates
            cleaned_container_ids = set()
            containers_to_delete = []
            
            for conflicting in conflicting_containers:
                # Skip if we already cleaned up this container
                if conflicting.id in cleaned_container_ids:
                    continue
                
                cleaned_container_ids.add(conflicting.id)
                
                current_app.logger.info(
                    f"Found conflicting container {conflicting.container_name} "
                    f"(proxy_path: {conflicting.proxy_path}, status: {conflicting.status}), cleaning up"
                )
                # Try to remove the Docker container if it exists
                proceed_with_db_cleanup = False
                if conflicting.container_id:
                    try:
                        container = self.client.containers.get(conflicting.container_id)
                        container.remove(force=True)
                        current_app.logger.info(f"Removed conflicting Docker container {conflicting.container_id}")
                        proceed_with_db_cleanup = True
                    except NotFound:
                        current_app.logger.info(f"Conflicting Docker container {conflicting.container_id} not found")
                        proceed_with_db_cleanup = True
                    except Exception as e:
                        current_app.logger.warning(f"Failed to remove conflicting Docker container: {str(e)}")
                        # Continue anyway - we'll try to remove the DB record
                        proceed_with_db_cleanup = True
                else:
                    proceed_with_db_cleanup = True
                
                if proceed_with_db_cleanup:
                    containers_to_delete.append(conflicting)
            
            # Batch delete all conflicting containers in a single commit
            if containers_to_delete:
                for conflicting in containers_to_delete:
                    db.session.delete(conflicting)
                db.session.commit()
                current_app.logger.info(f"Removed {len(containers_to_delete)} conflicting database records")
            
            # Also check if a Docker container with this name exists but isn't in our database
            try:
                existing_docker_container = self.client.containers.get(container_name)
                current_app.logger.info(
                    f"Found orphaned Docker container {container_name}, removing it"
                )
                existing_docker_container.remove(force=True)
                current_app.logger.info(f"Removed orphaned Docker container {container_name}")
            except NotFound:
                # Container doesn't exist in Docker, which is what we want
                pass
            except Exception as e:
                current_app.logger.warning(f"Error checking for orphaned Docker container: {str(e)}")
            
            # Find available host ports for both VNC and audio BEFORE creating database record
            # This prevents partial state where a container exists without ports
            try:
                # Allocate VNC port first
                host_port = self._find_available_port_locked()
                # Allocate audio port, excluding the VNC port we just allocated
                audio_host_port = self._find_available_port_locked(exclude_ports=[host_port])
                
                current_app.logger.info(f"Allocated ports - VNC: {host_port}, Audio: {audio_host_port}")
            except Exception as e:
                current_app.logger.error(f"Failed to allocate ports: {str(e)}")
                raise
            
            # Create database record with all information including ports
            container_record = Container(
                user_id=user_id,
                session_id=session_id,
                container_name=container_name,
                image_name=kasm_image,
                desktop_type=desktop_type,
                desktop_image_id=desktop_image_id,
                status='creating',
                container_port=container_port,
                host_port=host_port,
                audio_port=audio_host_port,
                proxy_path=proxy_path
            )
            db.session.add(container_record)
            db.session.commit()
            
            # Environment variables for Kasm
            environment = {
                'VNC_PW': os.environ.get('VNC_PASSWORD', 'password'),
                'USER': username,
                'START_PULSEAUDIO': '1',  # Ensure PulseAudio starts for audio capture
                'ISERV_PROFILE_SYNC': '1',  # Enable IServ bidirectional profile sync
                'ISERV_SYNC_INTERVAL': os.environ.get('ISERV_SYNC_INTERVAL', '30'),  # Sync interval in seconds
            }
            
            # Get user data directory - ensure it exists
            from app.utils.directory_manager import ensure_user_directory
            user_data_dir = ensure_user_directory(user_id)
            extern_user_data_dir = os.path.join(current_app.config.get('EXTERN_USERADATA_BASE_DIR'), str(user_id))
            
            # Prepare separated user private files and desktop-type-specific configs
            user_private_dir, user_config_dir = self._prepare_user_directories(user_id, kasm_image, desktop_type, username)
            
            # Get shared public directory from config
            extern_shared_public_dir = current_app.config.get('EXTERN_SHARED_DIR', '/data/shared/public')
            
            # Setup volumes with separated user private files and desktop-type-specific configs
            # We use an overlay approach: mount private user space, then overlay desktop configs
            volumes = {
                user_private_dir: {
                    'bind': '/home/kasm-user-private',
                    'mode': 'rw'
                },
                user_config_dir: {
                    'bind': '/home/kasm-user-configs',
                    'mode': 'rw'
                },
                extern_shared_public_dir: {
                    'bind': '/home/kasm-user/Public/shared',
                    'mode': 'rw'
                }
            }
            
            # Check for assignment with folder path
            if desktop_type_record:
                user = User.query.get(user_id)
                if user:
                    user_group_ids = [g.id for g in user.groups]
                    has_access, assignment = DesktopAssignment.check_access(
                        desktop_type_record.id, user_id, user_group_ids
                    )
                    
                    if assignment and assignment.assignment_folder_path:
                        # Get teacher's private folder path (inside PRIVATE subdirectory)
                        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
                        teacher_folder_path = os.path.join(
                            user_data_base,
                            str(assignment.created_by),
                            'PRIVATE',
                            assignment.assignment_folder_path
                        )
                        extern_user_data_base = current_app.config.get('EXTERN_USERADATA_BASE_DIR', '/data/users')
                        extern_teacher_folder_path = os.path.join(
                            extern_user_data_base,
                            str(assignment.created_by),
                            'PRIVATE',
                            assignment.assignment_folder_path
                        )
                        
                        current_app.logger.info(f"Assignment folder check - Path: {assignment.assignment_folder_path}")
                        current_app.logger.info(f"Teacher folder path (backend view): {teacher_folder_path}")
                        current_app.logger.info(f"Extern folder path (host): {extern_teacher_folder_path}")
                        current_app.logger.info(f"Folder exists: {os.path.exists(teacher_folder_path)}")
                        current_app.logger.info(f"Is directory: {os.path.isdir(teacher_folder_path) if os.path.exists(teacher_folder_path) else 'N/A'}")
                        
                        # Verify folder exists
                        if os.path.exists(teacher_folder_path) and os.path.isdir(teacher_folder_path):
                            # Mount as read-only in /home/kasm-user/Public/[folder-name]
                            folder_name = assignment.assignment_folder_name or assignment.assignment_folder_path.split('/')[-1]
                            volumes[extern_teacher_folder_path] = {
                                'bind': f'/home/kasm-user/Public/{folder_name}',
                                'mode': 'ro'  # Read-only
                            }
                            current_app.logger.info(
                                f"Mounting assignment folder: {extern_teacher_folder_path} -> /home/kasm-user/Public/{folder_name} (read-only)"
                            )
            
            # Create and start container
            current_app.logger.info(f"Creating container {container_name} from image {kasm_image}")
            
            # Add startup command to merge private user space and desktop configs into /home/kasm-user
            # This implements an overlayFS-like behavior where:
            # 1. Private user files (shared across all containers) are copied first as the base layer
            # 2. Desktop-type-specific configs are overlaid on top (with -n to not overwrite)
            startup_script = (
                '#!/bin/bash\n'
                '# Merge private user space into home directory (shared across all containers)\n'
                'if [ -d /home/kasm-user-private ]; then\n'
                '  cp -a /home/kasm-user-private/. /home/kasm-user/ 2>/dev/null || true\n'
                'fi\n'
                '# Overlay desktop-type-specific configs on top (without overwriting private files)\n'
                'if [ -d /home/kasm-user-configs ]; then\n'
                '  cp -an /home/kasm-user-configs/. /home/kasm-user/ 2>/dev/null || true\n'
                'fi\n'
                '# Execute original entrypoint\n'
                'exec /dockerstartup/kasm_default_profile.sh /dockerstartup/vnc_startup.sh\n'
            )
            
            container = self.client.containers.run(
                kasm_image,
                name=container_name,
                entrypoint=['/bin/bash', '-c', startup_script],
                ports={
                    f'{container_port}/tcp': host_port,  # VNC port (6901) → 7000+
                    '4901/tcp': audio_host_port  # Audio WebSocket port (4901) → 7000+
                },
                environment=environment,
                detach=True,
                remove=False,
                shm_size='512m',  # Increased shared memory for browser
                volumes=volumes,
                labels={
                    'user_id': user_id,
                    'session_id': session_id,
                    'managed_by': 'iserv-remote-desktop',
                    'audio_port': str(audio_host_port)
                }
            )
            
            # Update container record
            container_record.container_id = container.id
            container_record.host_port = host_port
            container_record.status = 'running'
            container_record.started_at = datetime.now(timezone.utc)
            db.session.commit()
            
            current_app.logger.info(
                f"Container {container_name} created successfully on port {host_port}"
            )
            
            # Emit WebSocket event for real-time updates
            _emit_container_created(container_record, user_id)
            
            return container_record
            
        except APIError as e:
            current_app.logger.error(f"Docker API error: {str(e)}")
            # Rollback any pending changes
            db.session.rollback()
            # Try to update status in a fresh transaction
            if container_record and container_record.id:
                try:
                    # Refresh the object from database to avoid stale state
                    db.session.expire(container_record)
                    container_record = Container.query.get(container_record.id)
                    if container_record:
                        container_record.status = 'error'
                        db.session.commit()
                except Exception as commit_error:
                    current_app.logger.error(f"Failed to update container status after error: {str(commit_error)}")
                    db.session.rollback()
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to create container: {str(e)}")
            # Rollback any pending changes
            db.session.rollback()
            # Try to update status in a fresh transaction
            if container_record and container_record.id:
                try:
                    # Refresh the object from database to avoid stale state
                    db.session.expire(container_record)
                    container_record = Container.query.get(container_record.id)
                    if container_record:
                        container_record.status = 'error'
                        db.session.commit()
                except Exception as commit_error:
                    current_app.logger.error(f"Failed to update container status after error: {str(commit_error)}")
                    db.session.rollback()
            raise
    
    def stop_container(self, container_record):
        """
        Stop a running container
        
        Args:
            container_record: Container model instance
        """
        try:
            user_id = container_record.user_id
            if not container_record.container_id:
                current_app.logger.warning(
                    f"No container ID for {container_record.container_name}"
                )
                return
            
            container = self.client.containers.get(container_record.container_id)
            container.stop(timeout=10)
            
            container_record.status = 'stopped'
            container_record.stopped_at = datetime.now(timezone.utc)
            db.session.commit()
            
            current_app.logger.info(
                f"Container {container_record.container_name} stopped"
            )
            
            # Emit WebSocket event for real-time updates
            _emit_container_stopped(container_record, user_id)
            
        except NotFound:
            current_app.logger.warning(
                f"Container {container_record.container_id} not found in Docker"
            )
            container_record.status = 'stopped'
            db.session.commit()
            # Still emit the event
            _emit_container_stopped(container_record, container_record.user_id)
        except Exception as e:
            current_app.logger.error(f"Failed to stop container: {str(e)}")
            db.session.rollback()
            raise
    
    def remove_container(self, container_record):
        """
        Remove a container
        
        Args:
            container_record: Container model instance
        """
        try:
            if container_record.container_id:
                try:
                    container = self.client.containers.get(container_record.container_id)
                    container.remove(force=True)
                    current_app.logger.info(
                        f"Container {container_record.container_name} removed"
                    )
                except NotFound:
                    current_app.logger.warning(
                        f"Container {container_record.container_id} not found in Docker"
                    )
            
            # Remove from database
            db.session.delete(container_record)
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Failed to remove container: {str(e)}")
            db.session.rollback()
            raise
    
    def get_container_status(self, container_record):
        """
        Get current status of a container
        
        Args:
            container_record: Container model instance
            
        Returns:
            dict with status information
        """
        try:
            if not container_record.container_id:
                return {'status': container_record.status, 'docker_status': 'unknown'}
            
            container = self.client.containers.get(container_record.container_id)
            docker_status = container.status
            
            # Update database if status changed
            if docker_status == 'running' and container_record.status != 'running':
                container_record.status = 'running'
                container_record.started_at = datetime.now(timezone.utc)
                db.session.commit()
            elif docker_status in ['exited', 'dead'] and container_record.status != 'stopped':
                container_record.status = 'stopped'
                container_record.stopped_at = datetime.now(timezone.utc)
                db.session.commit()
            
            return {
                'status': container_record.status,
                'docker_status': docker_status,
                'host_port': container_record.host_port,
                'created_at': container_record.created_at.isoformat() if container_record.created_at else None
            }
            
        except NotFound:
            container_record.status = 'stopped'
            db.session.commit()
            return {'status': 'stopped', 'docker_status': 'not_found'}
        except Exception as e:
            current_app.logger.error(f"Failed to get container status: {str(e)}")
            db.session.rollback()
            return {'status': 'error', 'docker_status': 'error', 'error': str(e)}
    
    def cleanup_stopped_containers(self):
        """Remove stopped containers older than configured time"""
        try:
            from datetime import timedelta
            
            # Get all stopped containers older than 1 hour
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            old_containers = Container.query.filter(
                Container.status == 'stopped',
                Container.stopped_at < cutoff_time
            ).all()
            
            for container in old_containers:
                self.remove_container(container)
            
            current_app.logger.info(f"Cleaned up {len(old_containers)} stopped containers")
            
        except Exception as e:
            current_app.logger.error(f"Failed to cleanup containers: {str(e)}")
            db.session.rollback()
    
    def stop_idle_containers(self, idle_hours=1.5):
        """
        Stop containers that haven't been accessed for the specified time
        
        Args:
            idle_hours: Number of hours of inactivity before stopping (default: 1.5 = 90 minutes)
        """
        try:
            from datetime import timedelta
            
            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=idle_hours)
            
            # Get all running containers that haven't been accessed recently
            # Use OR condition to catch containers with NULL last_accessed (treat as very old)
            idle_containers = Container.query.filter(
                Container.status == 'running',
                or_(
                    Container.last_accessed < cutoff_time,
                    Container.last_accessed.is_(None)
                )
            ).all()
            
            stopped_count = 0
            for container in idle_containers:
                try:
                    # Initialize last_accessed if it's NULL (for backwards compatibility)
                    if container.last_accessed is None:
                        container.last_accessed = container.started_at or container.created_at or datetime.now(timezone.utc)
                        db.session.commit()
                        current_app.logger.info(
                            f"Initialized last_accessed for container {container.container_name}"
                        )
                    
                    # Verify it's still running in Docker before stopping
                    status_info = self.get_container_status(container)
                    if status_info.get('status') == 'running':
                        self.stop_container(container)
                        stopped_count += 1
                        current_app.logger.info(
                            f"Stopped idle container {container.container_name} "
                            f"(last accessed: {container.last_accessed}, cutoff: {cutoff_time})"
                        )
                except Exception as e:
                    current_app.logger.error(
                        f"Failed to stop idle container {container.container_name}: {str(e)}"
                    )
                    continue
            
            if stopped_count > 0:
                current_app.logger.info(
                    f"Auto-stopped {stopped_count} idle containers (idle > {idle_hours} hours)"
                )
            
            return stopped_count
            
        except Exception as e:
            current_app.logger.error(f"Failed to check idle containers: {str(e)}")
            db.session.rollback()
            return 0
    
    def _find_available_port_locked(self, start_port=7000, end_port=10000, exclude_ports=None):
        """
        Find an available port with database row-level locking to prevent race conditions
        
        Args:
            start_port: Starting port number
            end_port: Ending port number
            exclude_ports: List of ports to exclude (e.g., already allocated in this session)
            
        Returns:
            Available port number
        """
        if exclude_ports is None:
            exclude_ports = []
        
        # Use row-level locking (SELECT FOR UPDATE) to prevent race conditions
        # This ensures only one thread can allocate a port at a time
        # Do NOT use skip_locked so concurrent requests wait for each other
        
        # Get all currently used ports from database with row-level lock
        used_ports = set(exclude_ports)  # Start with excluded ports
        containers = Container.query.filter(
            Container.status.in_(['running', 'creating', 'stopped', 'error']),
            or_(
                Container.host_port.isnot(None),
                Container.audio_port.isnot(None)
            )
        ).with_for_update().all()
        
        for container in containers:
            # Add both VNC and audio ports from database
            if container.host_port:
                used_ports.add(container.host_port)
            if container.audio_port:
                used_ports.add(container.audio_port)
        
        # Use a random offset to reduce collisions when multiple requests arrive simultaneously
        port_range = end_port - start_port
        offset = random.randint(0, port_range - 1)
        
        # Find available port by checking both database and actual port availability
        for i in range(port_range):
            port = start_port + (offset + i) % port_range
            # Skip if already in database or excluded
            if port in used_ports:
                continue
            
            # Check if port is actually free on the host system
            if self._is_port_available(port):
                return port
        
        raise Exception(f"No available ports in range {start_port}-{end_port}")
    
    def _find_available_port(self, start_port=7000, end_port=10000, exclude_ports=None):
        """
        Find an available port in the specified range by checking both database and host system
        (Non-locking version for backward compatibility)
        
        Args:
            start_port: Starting port number
            end_port: Ending port number
            exclude_ports: List of ports to exclude (e.g., already allocated in this session)
            
        Returns:
            Available port number
        """
        if exclude_ports is None:
            exclude_ports = []
        
        # Get all currently used ports from database (both VNC and audio)
        used_ports = set(exclude_ports)  # Start with excluded ports
        containers = Container.query.filter(
            Container.status.in_(['running', 'creating', 'stopped', 'error']),
            or_(
                Container.host_port.isnot(None),
                Container.audio_port.isnot(None)
            )
        ).all()
        
        for container in containers:
            if container.host_port:
                used_ports.add(container.host_port)
            if container.audio_port:
                used_ports.add(container.audio_port)
        
        # Use a random offset to reduce collisions when multiple requests arrive simultaneously
        port_range = end_port - start_port
        offset = random.randint(0, port_range - 1)
        
        # Find available port by checking both database and actual port availability
        for i in range(port_range):
            port = start_port + (offset + i) % port_range
            # Skip if already in database or excluded
            if port in used_ports:
                continue
            
            # Check if port is actually free on the host system
            if self._is_port_available(port):
                return port
        
        raise Exception(f"No available ports in range {start_port}-{end_port}")
    
    def _is_port_available(self, port):
        """
        Check if a port is available on the host system
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is available, False otherwise
        """
        try:
            # Try to bind to the port without SO_REUSEADDR to accurately detect in-use ports
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)  # 1 second timeout
                s.bind(('0.0.0.0', port))
                return True
        except (OSError, socket.timeout):
            # Port is already in use or timeout
            return False
    
    def _prepare_user_directories(self, user_id, image_name, desktop_type, username):
        """
        Prepare separated user directories for private files and desktop-type-specific configs.
        
        Directory structure:
        - /data/users/{user_id}/PRIVATE/ - User's private files (shared across all containers)
        - /data/users/{user_id}/{desktop_type}/ - Desktop-type-specific configs (.config, .cache, etc.)
        - /data/templates/{image_name}/ - Centralized default configs (shared across all users)
        
        Each desktop type has its own config directory so users can have different settings
        for different desktop environments (e.g., ubuntu-desktop vs filius-desktop).
        
        Args:
            user_id: User ID
            image_name: Docker image name (e.g., 'teacherki/kasm-desktop:latest')
            desktop_type: Desktop type name (e.g., 'ubuntu-desktop', 'filius-desktop')
            username: Username for logging
            
        Returns:
            Tuple of (user_private_dir_extern, user_config_dir_extern) - paths on the host
        """
        try:
            # Normalize image name for directory use (replace / and : with -)
            image_dir_name = image_name.replace('/', '-').replace(':', '-')
            
            # Get base paths
            user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
            extern_user_data_base = current_app.config.get('EXTERN_USERADATA_BASE_DIR', '/data/users')
            template_data_base = current_app.config.get('TEMPLATE_DATA_BASE_DIR', '/data/templates')
            
            # Define directory paths (backend view)
            user_base_dir = os.path.join(user_data_base, str(user_id))
            user_private_dir = os.path.join(user_base_dir, 'PRIVATE')
            # Use desktop_type for config directory (not full container name)
            user_config_dir = os.path.join(user_base_dir, desktop_type)
            config_template_dir = os.path.join(template_data_base, image_dir_name)
            
            # External paths (host view - for Docker mounts)
            extern_user_private_dir = os.path.join(extern_user_data_base, str(user_id), 'PRIVATE')
            extern_user_config_dir = os.path.join(extern_user_data_base, str(user_id), desktop_type)
            
            # Create directories if they don't exist
            os.makedirs(user_private_dir, exist_ok=True)
            os.makedirs(user_config_dir, exist_ok=True)
            # Note: config_template_dir is in centralized location, created separately
            
            # Set proper permissions
            container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
            container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
            
            for dir_path in [user_private_dir, user_config_dir]:
                os.chown(dir_path, container_uid, container_gid)
                os.chmod(dir_path, 0o755)
            
            # Check if centralized config template exists for this image
            template_initialized = os.path.join(config_template_dir, '.template_initialized')
            if not os.path.exists(template_initialized):
                current_app.logger.info(f"Extracting config template for image {image_name} to centralized location")
                # Create template directory if it doesn't exist
                os.makedirs(config_template_dir, exist_ok=True)
                os.chown(config_template_dir, container_uid, container_gid)
                os.chmod(config_template_dir, 0o755)
                self._extract_config_template(image_name, config_template_dir, image_dir_name)
            
            # Initialize user's config directory from centralized template if empty
            if not os.listdir(user_config_dir):
                current_app.logger.info(f"Initializing desktop configs from centralized template for {username}/{desktop_type}")
                self._copy_template_to_user_config(config_template_dir, user_config_dir)
            
            # Ensure standard user directories exist in PRIVATE dir (shared across all containers)
            standard_dirs = ['Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 'Videos', 'Public', 'PDF']
            for dir_name in standard_dirs:
                dir_path = os.path.join(user_private_dir, dir_name)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    os.chown(dir_path, container_uid, container_gid)
                    os.chmod(dir_path, 0o755)
            
            current_app.logger.info(
                f"User directories prepared - Private: {extern_user_private_dir}, Configs: {extern_user_config_dir}"
            )
            
            return extern_user_private_dir, extern_user_config_dir
            
        except Exception as e:
            current_app.logger.error(f"Failed to prepare user directories: {str(e)}")
            raise
    
    def _extract_config_template(self, image_name, template_dir, image_dir_name):
        """
        Extract default config files from a Docker image to use as template.
        
        Args:
            image_name: Docker image name
            template_dir: Directory to save template files
            image_dir_name: Sanitized image name for temp container
        """
        temp_container_name = f"temp-extract-{image_dir_name}-{os.urandom(4).hex()}"
        
        try:
            # Create a temporary container
            current_app.logger.info(f"Creating temporary container to extract configs from {image_name}")
            temp_container = self.client.containers.create(
                image_name,
                name=temp_container_name            )
            
            try:
                # Start the container briefly to let initialization happen
                temp_container.start()
                
                # Wait for startup scripts to run
                import time
                time.sleep(3)
                
                # Stop it
                temp_container.stop(timeout=5)
                
                # Extract the home directory structure
                bits, stat = temp_container.get_archive('/home/kasm-user')
                
                # Extract tar stream
                tar_stream = io.BytesIO()
                for chunk in bits:
                    tar_stream.write(chunk)
                tar_stream.seek(0)
                
                container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
                container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
                
                # Extract all hidden files and directories (those starting with '.')
                with tarfile.open(fileobj=tar_stream) as tar:
                    for member in tar.getmembers():
                        # Skip the root directory itself
                        if member.name == 'kasm-user':
                            continue
                        
                        # Remove 'kasm-user/' prefix from path
                        if member.name.startswith('kasm-user/'):
                            relative_path = member.name[len('kasm-user/'):]
                        else:
                            relative_path = member.name
                        
                        # Only extract hidden files/directories (starting with '.')
                        # Get the first component of the path
                        first_component = relative_path.split('/')[0]
                        if not first_component.startswith('.'):
                            continue
                        
                        target_path = os.path.join(template_dir, relative_path)
                        
                        if member.isdir():
                            os.makedirs(target_path, exist_ok=True)
                            os.chown(target_path, container_uid, container_gid)
                        elif member.isfile():
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as f:
                                f.write(tar.extractfile(member).read())
                            os.chown(target_path, container_uid, container_gid)
                            os.chmod(target_path, member.mode)
                
                # Mark template as initialized
                template_initialized = os.path.join(template_dir, '.template_initialized')
                with open(template_initialized, 'w') as f:
                    f.write(f"Template extracted from {image_name} at {datetime.now(timezone.utc).isoformat()}\n")
                os.chown(template_initialized, container_uid, container_gid)
                
                current_app.logger.info(f"Successfully extracted config template for {image_name}")
                
            finally:
                # Clean up temporary container
                temp_container.remove(force=True)
                current_app.logger.debug(f"Removed temporary container {temp_container_name}")
                
        except Exception as e:
            current_app.logger.error(f"Failed to extract config template: {str(e)}")
            # Try to clean up
            try:
                temp_container = self.client.containers.get(temp_container_name)
                temp_container.remove(force=True)
            except:
                pass
            raise
    
    def _copy_template_to_user_config(self, template_dir, user_config_dir):
        """
        Copy template configs to user's config directory.
        
        Args:
            template_dir: Source template directory
            user_config_dir: Destination user config directory
        """
        try:
            
            container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
            container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
            
            # Copy all files from template to user config
            for item in os.listdir(template_dir):
                # Skip the marker file
                if item == '.template_initialized':
                    continue
                
                src = os.path.join(template_dir, item)
                dst = os.path.join(user_config_dir, item)
                
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    # Set ownership recursively
                    for root, dirs, files in os.walk(dst):
                        os.chown(root, container_uid, container_gid)
                        for file in files:
                            file_path = os.path.join(root, file)
                            os.chown(file_path, container_uid, container_gid)
                else:
                    shutil.copy2(src, dst)
                    os.chown(dst, container_uid, container_gid)
            
            current_app.logger.info("Successfully copied template to user config directory")
            
        except Exception as e:
            current_app.logger.error(f"Failed to copy template to user config: {str(e)}")
            raise
    
    def reset_user_config(self, user_id, image_name):
        """
        Reset user's config for a specific desktop type to the default template.
        Fetches from centralized template directory.
        
        Args:
            user_id: User ID
            image_name: Docker image name
            
        Returns:
            Dict with success status and message
        """
        try:
            # Find the desktop type for this image
            desktop_image = DesktopImage.query.filter_by(docker_image=image_name).first()
            if not desktop_image:
                return {
                    'success': False,
                    'error': f'Desktop image {image_name} not found in database'
                }
            
            desktop_type = desktop_image.name
            
            # Normalize image name for template directory
            image_dir_name = image_name.replace('/', '-').replace(':', '-')
            
            # Get paths
            user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
            template_data_base = current_app.config.get('TEMPLATE_DATA_BASE_DIR', '/data/templates')
            # User configs are now stored by desktop_type, not image name
            user_config_dir = os.path.join(user_data_base, str(user_id), desktop_type)
            config_template_dir = os.path.join(template_data_base, image_dir_name)
            
            # Check if centralized template exists
            if not os.path.exists(config_template_dir):
                return {
                    'success': False,
                    'error': f'No config template found for image {image_name} in centralized template directory'
                }
            
            # Remove old config directory if it exists
            if os.path.exists(user_config_dir):
                shutil.rmtree(user_config_dir)
                current_app.logger.info(f"Removed old config directory {user_config_dir}")
            
            # Recreate config directory
            os.makedirs(user_config_dir, exist_ok=True)
            
            # Copy centralized template to user config
            self._copy_template_to_user_config(config_template_dir, user_config_dir)
            
            current_app.logger.info(f"Reset config for user {user_id}, desktop type {desktop_type} (image {image_name}) from centralized template")
            
            return {
                'success': True,
                'message': f'Config reset to default for {desktop_type}'
            }
            
        except Exception as e:
            current_app.logger.error(f"Failed to reset user config: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def refresh_config_template(self, image_name):
        """
        Re-extract config template from an image to centralized location (useful after image updates).
        
        Args:
            image_name: Docker image name
            
        Returns:
            Dict with success status and message
        """
        try:
            # Emit started event
            try:
                from app.routes.websocket_routes import emit_template_refresh_event
                emit_template_refresh_event('template_refresh_started', {
                    'image': image_name,
                    'message': f'Starting template refresh for {image_name}'
                })
            except Exception as e:
                current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")
            
            # Normalize image name
            image_dir_name = image_name.replace('/', '-').replace(':', '-')
            
            # Get centralized template directory
            template_data_base = current_app.config.get('TEMPLATE_DATA_BASE_DIR', '/data/templates')
            template_dir = os.path.join(template_data_base, image_dir_name)
            
            # Emit progress - Removing old template
            try:
                from app.routes.websocket_routes import emit_template_refresh_event
                emit_template_refresh_event('template_refresh_progress', {
                    'image': image_name,
                    'message': 'Removing old template...',
                    'status': 'Cleaning'
                })
            except Exception as e:
                current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")
            
            # Remove old template if exists
            if os.path.exists(template_dir):
                shutil.rmtree(template_dir)
                current_app.logger.info(f"Removed old centralized template {template_dir}")
            
            # Emit progress - Creating new template
            try:
                from app.routes.websocket_routes import emit_template_refresh_event
                emit_template_refresh_event('template_refresh_progress', {
                    'image': image_name,
                    'message': 'Creating template directory...',
                    'status': 'Creating'
                })
            except Exception as e:
                current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")
            
            # Extract new template to centralized location
            os.makedirs(template_dir, exist_ok=True)
            container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
            container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
            os.chown(template_dir, container_uid, container_gid)
            os.chmod(template_dir, 0o755)
            
            # Emit progress - Extracting template
            try:
                from app.routes.websocket_routes import emit_template_refresh_event
                emit_template_refresh_event('template_refresh_progress', {
                    'image': image_name,
                    'message': 'Extracting configuration from image...',
                    'status': 'Extracting'
                })
            except Exception as e:
                current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")
            
            self._extract_config_template(image_name, template_dir, image_dir_name)
            
            current_app.logger.info(f"Refreshed centralized config template for {image_name}")
            
            # Emit completed event
            try:
                from app.routes.websocket_routes import emit_template_refresh_event
                emit_template_refresh_event('template_refresh_completed', {
                    'image': image_name,
                    'message': f'Template refresh completed for {image_name}'
                })
            except Exception as e:
                current_app.logger.debug(f"WebSocket emit failed (non-critical): {e}")
            
            return {
                'success': True,
                'message': f'Centralized config template refreshed for {image_name}',
                'template_location': template_dir
            }
            
        except Exception as e:
            current_app.logger.error(f"Failed to refresh config template: {str(e)}")
            
            # Emit error event
            try:
                from app.routes.websocket_routes import emit_template_refresh_event
                emit_template_refresh_event('template_refresh_error', {
                    'image': image_name,
                    'error': str(e)
                })
            except Exception as ws_error:
                current_app.logger.debug(f"WebSocket emit failed (non-critical): {ws_error}")
            
            return {
                'success': False,
                'error': str(e)
            }

    
    def _initialize_user_configs(self, user_data_dir, image_name, username):
        """
        Initialize default configuration files in user's home directory if missing.
        This ensures .config and other essential files are present even if user deleted them.
        
        Args:
            user_data_dir: Path to user's data directory on host
            image_name: Docker image name to extract defaults from
            username: Username for the container
        """
        try:
            # Check if .config directory exists
            config_dir = os.path.join(user_data_dir, '.config')
            
            # If .config exists and has content, assume configs are okay
            if os.path.exists(config_dir) and os.listdir(config_dir):
                current_app.logger.debug(f"User configs exist for {username}, skipping initialization")
                return
            
            current_app.logger.info(f"Initializing default configs for user {username} from image {image_name}")
            
            # Create a temporary container to copy default files from
            temp_container_name = f"temp-init-{username}-{os.urandom(4).hex()}"
            
            try:
                # Create a temporary container (don't start it)
                temp_container = self.client.containers.create(
                    image_name,
                    name=temp_container_name,
                    entrypoint=['/bin/sh', '-c', 'sleep 1']  # Dummy command
                )
                
                try:
                    # Start the container briefly to let initialization happen
                    temp_container.start()
                    
                    # Wait a moment for any startup scripts to run
                    import time
                    time.sleep(2)
                    
                    # Stop it
                    temp_container.stop(timeout=5)
                    
                    # Export the home directory structure
                    # Get the tar archive of /home/kasm-user
                    import tarfile
                    import io
                    
                    bits, stat = temp_container.get_archive('/home/kasm-user')
                    
                    # Extract tar stream to user's directory
                    tar_stream = io.BytesIO()
                    for chunk in bits:
                        tar_stream.write(chunk)
                    tar_stream.seek(0)
                    
                    # Open tar and extract only if files don't exist
                    with tarfile.open(fileobj=tar_stream) as tar:
                        for member in tar.getmembers():
                            # Skip the root directory itself
                            if member.name == 'kasm-user':
                                continue
                            
                            # Remove 'kasm-user/' prefix from path
                            if member.name.startswith('kasm-user/'):
                                relative_path = member.name[len('kasm-user/'):]
                            else:
                                relative_path = member.name
                            
                            target_path = os.path.join(user_data_dir, relative_path)
                            
                            # Only extract if target doesn't exist
                            if not os.path.exists(target_path):
                                if member.isdir():
                                    os.makedirs(target_path, exist_ok=True)
                                    # Set ownership
                                    container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
                                    container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
                                    os.chown(target_path, container_uid, container_gid)
                                elif member.isfile():
                                    # Extract file
                                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                    with open(target_path, 'wb') as f:
                                        f.write(tar.extractfile(member).read())
                                    # Set ownership
                                    container_uid = current_app.config.get('CONTAINER_USER_ID', 1000)
                                    container_gid = current_app.config.get('CONTAINER_GROUP_ID', 1000)
                                    os.chown(target_path, container_uid, container_gid)
                                    # Preserve permissions
                                    os.chmod(target_path, member.mode)
                    
                    current_app.logger.info(f"Successfully initialized default configs for {username}")
                    
                finally:
                    # Clean up temporary container
                    temp_container.remove(force=True)
                    current_app.logger.debug(f"Removed temporary init container {temp_container_name}")
                    
            except Exception as e:
                current_app.logger.error(f"Failed to initialize configs from temp container: {str(e)}")
                # Try to clean up temp container if it exists
                try:
                    temp_container = self.client.containers.get(temp_container_name)
                    temp_container.remove(force=True)
                except:
                    pass
                # Don't raise - allow container creation to proceed even if config init fails
                
        except Exception as e:
            current_app.logger.warning(f"Could not initialize user configs: {str(e)}")
            # Don't raise - this is a best-effort initialization
    
    def sync_database_with_docker(self):
        """
        Synchronize database with actual Docker state and clean up inconsistencies.
        This should be run regularly (e.g., every 5 minutes) to:
        - Remove DB records for containers that don't exist in Docker
        - Update status of containers that changed state
        - Clean up containers stuck in 'creating' state for too long
        - Normalize proxy_path to lowercase format
        
        Returns:
            dict with cleanup statistics
        """
        try:
            stats = {
                'checked': 0,
                'removed_orphaned': 0,
                'updated_status': 0,
                'cleaned_stuck': 0,
                'normalized_paths': 0,
                'errors': 0
            }
            
            # Get all containers from database (excluding already stopped ones older than 1 hour)
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            containers = Container.query.filter(
                or_(
                    Container.status != 'stopped',
                    Container.stopped_at > cutoff_time
                )
            ).all()
            
            stats['checked'] = len(containers)
            current_app.logger.info(f"Starting database sync check for {len(containers)} containers")
            
            # Get all Docker containers managed by us
            docker_containers = {}
            try:
                all_docker = self.client.containers.list(
                    all=True,
                    filters={'label': 'managed_by=iserv-remote-desktop'}
                )
                docker_containers = {c.id: c for c in all_docker}
            except Exception as e:
                current_app.logger.error(f"Failed to list Docker containers: {str(e)}")
            
            for container in containers:
                try:
                    # Check 1: Normalize proxy_path to lowercase
                    if container.proxy_path:
                        normalized = container.proxy_path.lower()
                        if container.proxy_path != normalized:
                            current_app.logger.info(
                                f"Normalizing proxy_path: '{container.proxy_path}' -> '{normalized}'"
                            )
                            container.proxy_path = normalized
                            stats['normalized_paths'] += 1
                    
                    # Check 2: Populate audio_port from Docker labels if missing
                    if container.container_id and not container.audio_port:
                        docker_container = docker_containers.get(container.container_id)
                        if docker_container:
                            audio_port_str = docker_container.labels.get('audio_port')
                            if audio_port_str:
                                try:
                                    container.audio_port = int(audio_port_str)
                                    stats['normalized_paths'] += 1  # Reuse this counter for migrations
                                    current_app.logger.info(
                                        f"Populated audio_port from Docker labels for {container.container_name}: {audio_port_str}"
                                    )
                                except ValueError:
                                    pass
                    
                    # Check 3: Clean up containers stuck in 'creating' for more than 5 minutes
                    if container.status == 'creating':
                        time_in_creating = datetime.now(timezone.utc) - container.created_at
                        if time_in_creating > timedelta(minutes=5):
                            current_app.logger.warning(
                                f"Container {container.container_name} stuck in 'creating' for "
                                f"{time_in_creating.total_seconds():.0f}s, cleaning up"
                            )
                            
                            # Try to remove Docker container if it exists
                            if container.container_id:
                                try:
                                    docker_container = self.client.containers.get(container.container_id)
                                    docker_container.remove(force=True)
                                    current_app.logger.info(f"Removed stuck Docker container {container.container_id}")
                                except NotFound:
                                    pass
                                except Exception as e:
                                    current_app.logger.warning(f"Failed to remove stuck container: {str(e)}")
                            
                            # Remove from database
                            db.session.delete(container)
                            stats['cleaned_stuck'] += 1
                            continue
                    
                    # Check 4: Verify container exists in Docker and sync status
                    if container.container_id:
                        docker_container = docker_containers.get(container.container_id)
                        
                        if not docker_container:
                            # Container exists in DB but not in Docker
                            current_app.logger.warning(
                                f"Container {container.container_name} (ID: {container.container_id}) "
                                f"not found in Docker, removing from database"
                            )
                            db.session.delete(container)
                            stats['removed_orphaned'] += 1
                            continue
                        
                        # Container exists, check if status needs updating
                        docker_status = docker_container.status
                        
                        if docker_status == 'running' and container.status != 'running':
                            container.status = 'running'
                            if not container.started_at:
                                container.started_at = datetime.now(timezone.utc)
                            stats['updated_status'] += 1
                            current_app.logger.info(
                                f"Updated container {container.container_name} status to 'running'"
                            )
                        elif docker_status in ['exited', 'dead'] and container.status != 'stopped':
                            container.status = 'stopped'
                            if not container.stopped_at:
                                container.stopped_at = datetime.now(timezone.utc)
                            stats['updated_status'] += 1
                            current_app.logger.info(
                                f"Updated container {container.container_name} status to 'stopped'"
                            )
                    
                    elif container.status in ['running', 'creating']:
                        # No container_id but marked as running/creating - orphaned record
                        current_app.logger.warning(
                            f"Container {container.container_name} has no container_id but status is "
                            f"'{container.status}', removing from database"
                        )
                        db.session.delete(container)
                        stats['removed_orphaned'] += 1
                        
                except Exception as e:
                    current_app.logger.error(
                        f"Error processing container {container.container_name}: {str(e)}"
                    )
                    stats['errors'] += 1
                    continue
            
            # Commit all changes
            db.session.commit()
            
            current_app.logger.info(
                f"Database sync completed: {stats['checked']} checked, "
                f"{stats['removed_orphaned']} orphaned removed, "
                f"{stats['updated_status']} status updated, "
                f"{stats['cleaned_stuck']} stuck cleaned, "
                f"{stats['normalized_paths']} paths normalized, "
                f"{stats['errors']} errors"
            )
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Database sync failed: {str(e)}")
            db.session.rollback()
            return {'error': str(e)}
    
    def get_container_url(self, container_record):
        """
        Get the URL to access the container via subdomain routing
        
        Apache routes subdomains directly to containers using RewriteMap.
        
        Args:
            container_record: Container model instance
            
        Returns:
            URL string with subdomain
        """
        if not container_record.proxy_path:
            return None
        
        # Get host from environment
        prefix = os.environ.get('CONTAINER_PREFIX', 'desktop')
        
        # Use subdomain routing: desktop-container-name.hub.mdg-hamburg.de
        # Format matches wildcard SSL cert *.hub.mdg-hamburg.de
        # Apache's RewriteMap queries Flask API to get container IP:port
        return f"https://{prefix}-{container_record.proxy_path}.hub.mdg-hamburg.de/"
    
    def pull_image(self, image_name, emit_callback=None):
        """
        Pull a Docker image with real-time progress updates
        
        Args:
            image_name: Name of the image to pull (e.g., 'kasmweb/ubuntu-jammy-desktop:1.15.0')
            emit_callback: Callback function to emit progress updates
                          Should accept (event, data) parameters
        
        Returns:
            Dict with success status and message
        """
        try:
            current_app.logger.info(f"Starting pull for image: {image_name}")
            
            if emit_callback:
                emit_callback('image_pull_started', {
                    'image': image_name,
                    'status': 'started',
                    'message': f'Starting pull for {image_name}'
                })
            
            # Pull the image with progress tracking
            response = self.client.api.pull(image_name, stream=True, decode=True)
            
            # Track layers to avoid duplicate progress messages
            last_progress = {}
            
            for line in response:
                if 'status' in line:
                    status = line['status']
                    layer_id = line.get('id', '')
                    progress = line.get('progress', '')
                    
                    # Create a unique key for this layer's status
                    progress_key = f"{layer_id}:{status}"
                    
                    # Only emit if progress changed for this layer
                    if progress and progress != last_progress.get(progress_key):
                        last_progress[progress_key] = progress
                        
                        if emit_callback:
                            emit_callback('image_pull_progress', {
                                'image': image_name,
                                'status': status,
                                'layer_id': layer_id,
                                'progress': progress,
                                'message': f'{status}: {layer_id} {progress}' if layer_id else status
                            })
                        
                        current_app.logger.debug(f"Pull progress: {status} - {layer_id} {progress}")
                    elif not layer_id and status:
                        # Status message without layer (e.g., "Downloading", "Extracting")
                        if emit_callback:
                            emit_callback('image_pull_progress', {
                                'image': image_name,
                                'status': status,
                                'message': status
                            })
                
                if 'error' in line:
                    error_msg = line['error']
                    current_app.logger.error(f"Error pulling image {image_name}: {error_msg}")
                    
                    if emit_callback:
                        emit_callback('image_pull_error', {
                            'image': image_name,
                            'status': 'error',
                            'error': error_msg
                        })
                    
                    return {
                        'success': False,
                        'error': error_msg
                    }
            
            current_app.logger.info(f"Successfully pulled image: {image_name}")
            
            if emit_callback:
                emit_callback('image_pull_completed', {
                    'image': image_name,
                    'status': 'completed',
                    'message': f'Successfully pulled {image_name}'
                })
            
            return {
                'success': True,
                'message': f'Successfully pulled {image_name}'
            }
            
        except Exception as e:
            error_msg = str(e)
            current_app.logger.error(f"Failed to pull image {image_name}: {error_msg}")
            
            if emit_callback:
                emit_callback('image_pull_error', {
                    'image': image_name,
                    'status': 'error',
                    'error': error_msg
                })
            
            return {
                'success': False,
                'error': error_msg
            }
