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
    
    def create_container(self, user_id, session_id, username):
        """
        Create and start a Kasm workspace container for a user
        
        Args:
            user_id: User's unique ID
            session_id: Session ID
            username: User's username
            
        Returns:
            Container model instance
        """
        container_record = None
        try:
            # Get configuration from environment
            kasm_image = os.environ.get('KASM_IMAGE', 'kasmweb/ubuntu-focal-desktop:1.15.0')
            container_port = int(os.environ.get('KASM_CONTAINER_PORT', 6901))
            
            # Generate unique container name
            container_name = f"kasm-{username}-{session_id[:8]}"
            
            # Check if container already exists in database
            existing = Container.query.filter_by(
                session_id=session_id,
                status='running'
            ).first()
            
            if existing:
                current_app.logger.info(f"Container already exists for session {session_id}")
                return existing
            
            # Create database record first
            container_record = Container(
                user_id=user_id,
                session_id=session_id,
                container_name=container_name,
                image_name=kasm_image,
                status='creating',
                container_port=container_port
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
                container_record.status = 'error'
                db.session.commit()
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to create container: {str(e)}")
            if container_record:
                container_record.status = 'error'
                db.session.commit()
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
    
    def _find_available_port(self, start_port=7000, end_port=8000):
        """
        Find an available port in the specified range
        
        Args:
            start_port: Starting port number
            end_port: Ending port number
            
        Returns:
            Available port number
        """
        # Get all currently used ports
        used_ports = set()
        containers = Container.query.filter(
            Container.status == 'running',
            Container.host_port.isnot(None)
        ).all()
        
        for container in containers:
            used_ports.add(container.host_port)
        
        # Find available port
        for port in range(start_port, end_port):
            if port not in used_ports:
                return port
        
        raise Exception(f"No available ports in range {start_port}-{end_port}")
    
    def get_container_url(self, container_record):
        """
        Get the URL to access the container
        
        Args:
            container_record: Container model instance
            
        Returns:
            URL string
        """
        if not container_record.host_port:
            return None
        
        # Get host from environment or use localhost
        host = os.environ.get('DOCKER_HOST_URL', 'localhost')
        
        return f"http://{host}:{container_record.host_port}"
