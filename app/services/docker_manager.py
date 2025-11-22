import docker
from docker.errors import DockerException, NotFound, APIError
from flask import current_app
import os
import random
from datetime import datetime, timezone
from app import db
from app.models.containers import Container

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
    
    def create_container(self, user_id, session_id, username, desktop_type=None):
        """
        Create and start a Kasm workspace container for a user
        
        Args:
            user_id: User's unique ID
            session_id: Session ID
            username: User's username
            desktop_type: Type of desktop to create (optional)
            
        Returns:
            Container model instance
        """
        container_record = None
        try:
            # Desktop type to image mapping
            DESKTOP_IMAGES = {
                'ubuntu-vscode': 'kasmweb/vs-code:1.15.0',
                'ubuntu-desktop': 'kasmweb/ubuntu-focal-desktop:1.15.0',
                'ubuntu-chromium': 'kasmweb/chromium:1.15.0'
            }
            
            # Get image based on desktop type or use default
            if desktop_type and desktop_type in DESKTOP_IMAGES:
                kasm_image = DESKTOP_IMAGES[desktop_type]
            else:
                kasm_image = os.environ.get('KASM_IMAGE', 'kasmweb/ubuntu-focal-desktop:1.15.0')
                desktop_type = 'ubuntu-desktop'  # Default type
            
            container_port = int(os.environ.get('KASM_CONTAINER_PORT', 6901))
            
            # Generate unique container name with desktop type
            container_name = f"kasm-{username}-{desktop_type}-{session_id[:8]}"
            
            # Generate unique proxy path for reverse proxy access
            proxy_path = f"{username}-{desktop_type}"
            
            # Check if container already exists for this session and desktop type in any state
            # We check by session_id, user_id, and desktop_type to ensure we only find containers for this user
            existing = Container.query.filter_by(
                session_id=session_id,
                user_id=user_id,
                desktop_type=desktop_type
            ).first()
            
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
            
            # Create database record first
            container_record = Container(
                user_id=user_id,
                session_id=session_id,
                container_name=container_name,
                image_name=kasm_image,
                desktop_type=desktop_type,
                status='creating',
                container_port=container_port,
                proxy_path=proxy_path
            )
            db.session.add(container_record)
            db.session.commit()
            
            # Find available host port
            host_port = self._find_available_port()
            
            # Environment variables for Kasm
            environment = {
                'VNC_PW': os.environ.get('VNC_PASSWORD', 'password'),
                'USER': username,
            }
            
            # Create and start container
            current_app.logger.info(f"Creating container {container_name} from image {kasm_image}")
            
            container = self.client.containers.run(
                kasm_image,
                name=container_name,
                ports={f'{container_port}/tcp': host_port},
                environment=environment,
                detach=True,
                remove=False,
                shm_size='512m',  # Increased shared memory for browser
                labels={
                    'user_id': user_id,
                    'session_id': session_id,
                    'managed_by': 'iserv-remote-desktop'
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
            
            return container_record
            
        except APIError as e:
            current_app.logger.error(f"Docker API error: {str(e)}")
            if container_record:
                try:
                    # Try to update status before rollback
                    container_record.status = 'error'
                    db.session.commit()
                except Exception as commit_error:
                    current_app.logger.error(f"Failed to update container status after error: {str(commit_error)}")
                    db.session.rollback()
            else:
                db.session.rollback()
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to create container: {str(e)}")
            if container_record:
                try:
                    # Try to update status before rollback
                    container_record.status = 'error'
                    db.session.commit()
                except Exception as commit_error:
                    current_app.logger.error(f"Failed to update container status after error: {str(commit_error)}")
                    db.session.rollback()
            else:
                db.session.rollback()
            raise
    
    def stop_container(self, container_record):
        """
        Stop a running container
        
        Args:
            container_record: Container model instance
        """
        try:
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
            
        except NotFound:
            current_app.logger.warning(
                f"Container {container_record.container_id} not found in Docker"
            )
            container_record.status = 'stopped'
            db.session.commit()
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
    
    def _find_available_port(self, start_port=7000, end_port=8000):
        """
        Find an available port in the specified range with database lock
        
        Args:
            start_port: Starting port number
            end_port: Ending port number
            
        Returns:
            Available port number
        """
        # Use database lock to prevent race conditions in port allocation
        from sqlalchemy import text
        
        # Get all currently used ports with a lock
        used_ports = set()
        containers = Container.query.filter(
            Container.status == 'running',
            Container.host_port.isnot(None)
        ).with_for_update().all()
        
        for container in containers:
            used_ports.add(container.host_port)
        
        # Find available port
        for port in range(start_port, end_port):
            if port not in used_ports:
                # Create a temporary lock record to reserve this port
                return port
        
        raise Exception(f"No available ports in range {start_port}-{end_port}")
    
    def get_container_url(self, container_record):
        """
        Get the URL to access the container via reverse proxy
        
        Args:
            container_record: Container model instance
            
        Returns:
            URL string
        """
        if not container_record.proxy_path:
            return None
        
        # Get host from environment
        host = os.environ.get('DOCKER_HOST_URL', 'localhost')
        
        # Use proxy path for access (reverse proxy will forward to the correct port)
        return f"http://{host}/desktop/{container_record.proxy_path}"
