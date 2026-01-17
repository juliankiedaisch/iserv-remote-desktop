import docker
from docker.errors import DockerException, NotFound, APIError
from flask import current_app
import os
import random
import socket
from datetime import datetime, timezone
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.containers import Container
from app.models.desktop_assignments import DesktopImage, DesktopAssignment
from app.models.users import User

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
            
            # Generate unique proxy path for reverse proxy access
            # Replace periods with dashes for DNS subdomain compatibility
            username_safe = username.replace('.', '-')
            proxy_path = f"{username_safe}-{desktop_type}"
            
            # Check if container already exists for this session and desktop type in any state
            # We check by session_id, user_id, and desktop_type to ensure we only find containers for this user
            # Use row-level locking to prevent concurrent creation attempts
            existing = Container.query.filter_by(
                session_id=session_id,
                user_id=user_id,
                desktop_type=desktop_type
            ).with_for_update(skip_locked=False).first()
            
            if existing:
                # If it's running, return it
                if existing.status == 'running':
                    current_app.logger.info(f"Container already exists for session {session_id} and type {desktop_type}")
                    return existing
                
                # If the existing container is in an error, stopped, or creating state, clean it up
                if existing.status in ['error', 'stopped', 'creating']:
                    current_app.logger.info(
                        f"Found existing container {existing.container_name} in state {existing.status}, cleaning up"
                    )
                    # Try to remove the Docker container if it exists
                    docker_removed = False
                    if existing.container_id:
                        try:
                            container = self.client.containers.get(existing.container_id)
                            container.remove(force=True)
                            current_app.logger.info(f"Removed existing Docker container {existing.container_id}")
                            docker_removed = True
                        except NotFound:
                            current_app.logger.info(f"Docker container {existing.container_id} not found")
                            docker_removed = True  # Container doesn't exist, safe to remove DB record
                        except Exception as e:
                            current_app.logger.warning(f"Failed to remove Docker container: {str(e)}")
                            # Don't remove DB record if Docker removal failed
                            raise Exception(
                                f"Cannot cleanup existing container '{existing.container_name}' (status: {existing.status}): "
                                f"Docker container removal failed"
                            ) from e
                    else:
                        # No Docker container ID, safe to remove DB record
                        docker_removed = True
                    
                    # Only remove the database record if Docker removal succeeded or container doesn't exist
                    if docker_removed:
                        db.session.delete(existing)
                        db.session.commit()
                        current_app.logger.info(f"Removed database record for container {existing.container_name}")
            
            # Also check for any containers with conflicting proxy_path or container_name
            # These could be from previous sessions that weren't properly cleaned up
            # Use row-level locking to prevent concurrent cleanup attempts
            conflicting_containers = Container.query.filter(
                or_(
                    Container.proxy_path == proxy_path,
                    Container.container_name == container_name
                ),
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
                proxy_path=proxy_path
            )
            db.session.add(container_record)
            db.session.commit()
            
            # Environment variables for Kasm
            environment = {
                'VNC_PW': os.environ.get('VNC_PASSWORD', 'password'),
                'USER': username,
                'START_PULSEAUDIO': '1',  # Ensure PulseAudio starts for audio capture
            }
            
            # Get user data directory - ensure it exists
            from app.utils.directory_manager import ensure_user_directory
            user_data_dir = ensure_user_directory(user_id)
            extern_user_data_dir = os.path.join(current_app.config.get('EXTERN_USERADATA_BASE_DIR'), str(user_id))
            
            # Get shared public directory from config
            extern_shared_public_dir = current_app.config.get('EXTERN_SHARED_DIR', '/data/shared/public')
            
            # Setup volumes
            volumes = {
                extern_user_data_dir: {
                    'bind': '/home/kasm-user',
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
                        # Get teacher's private folder path
                        user_data_base = current_app.config.get('USER_DATA_BASE_DIR', '/data/users')
                        teacher_folder_path = os.path.join(
                            user_data_base,
                            str(assignment.created_by),
                            assignment.assignment_folder_path
                        )
                        extern_user_data_base = current_app.config.get('EXTERN_USERADATA_BASE_DIR', '/data/users')
                        extern_teacher_folder_path = os.path.join(
                            extern_user_data_base,
                            str(assignment.created_by),
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
            
            container = self.client.containers.run(
                kasm_image,
                name=container_name,
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
    
    def stop_idle_containers(self, idle_hours=6):
        """
        Stop containers that haven't been accessed for the specified time
        
        Args:
            idle_hours: Number of hours of inactivity before stopping (default: 6)
        """
        try:
            from datetime import timedelta
            
            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=idle_hours)
            
            # Get all running containers that haven't been accessed recently
            idle_containers = Container.query.filter(
                Container.status == 'running',
                Container.last_accessed < cutoff_time
            ).all()
            
            stopped_count = 0
            for container in idle_containers:
                try:
                    # Verify it's still running in Docker before stopping
                    status_info = self.get_container_status(container)
                    if status_info.get('status') == 'running':
                        self.stop_container(container)
                        stopped_count += 1
                        current_app.logger.info(
                            f"Stopped idle container {container.container_name} "
                            f"(last accessed: {container.last_accessed})"
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
        # Use skip_locked to prevent blocking if another transaction has the lock
        from sqlalchemy import text
        
        # Get all currently used ports from database with row-level lock
        used_ports = set(exclude_ports)  # Start with excluded ports
        containers = Container.query.filter(
            Container.status.in_(['running', 'creating']),
            Container.host_port.isnot(None)
        ).with_for_update(skip_locked=True).all()
        
        for container in containers:
            used_ports.add(container.host_port)
        
        # Find available port by checking both database and actual port availability
        for port in range(start_port, end_port):
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
        
        # Get all currently used ports from database
        used_ports = set(exclude_ports)  # Start with excluded ports
        containers = Container.query.filter(
            Container.status.in_(['running', 'creating']),
            Container.host_port.isnot(None)
        ).all()
        
        for container in containers:
            used_ports.add(container.host_port)
        
        # Find available port by checking both database and actual port availability
        for port in range(start_port, end_port):
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
            # Try to bind to the port with timeout
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(1.0)  # 1 second timeout
                s.bind(('0.0.0.0', port))
                return True
        except (OSError, socket.timeout):
            # Port is already in use or timeout
            return False
    
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
                    
                    # Check 2: Clean up containers stuck in 'creating' for more than 5 minutes
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
                    
                    # Check 3: Verify container exists in Docker and sync status
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
