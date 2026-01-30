"""
Container Creation Queue Manager

This module implements a queue system to serialize container creation requests,
preventing race conditions and server errors when multiple users start containers simultaneously.
"""

import threading
import queue
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from flask import current_app

# Initialize logger
logger = logging.getLogger(__name__)


class ContainerCreationRequest:
    """Represents a container creation request in the queue"""
    
    def __init__(self, user_id: int, session_id: int, username: str, 
                 desktop_type: Optional[str] = None, 
                 desktop_image_id: Optional[int] = None,
                 callback: Optional[Callable] = None,
                 error_callback: Optional[Callable] = None):
        """
        Initialize a container creation request
        
        Args:
            user_id: User's unique ID
            session_id: Session ID
            username: User's username
            desktop_type: Type of desktop to create
            desktop_image_id: ID of the desktop image
            callback: Function to call on success with container as argument
            error_callback: Function to call on error with exception as argument
        """
        self.user_id = user_id
        self.session_id = session_id
        self.username = username
        self.desktop_type = desktop_type
        self.desktop_image_id = desktop_image_id
        self.callback = callback
        self.error_callback = error_callback
        self.timestamp = datetime.now()
        self.request_id = f"{username}_{session_id}_{self.timestamp.timestamp()}"
    
    def __repr__(self):
        return f"ContainerCreationRequest(user={self.username}, type={self.desktop_type}, id={self.request_id})"


class ContainerQueue:
    """
    Queue manager for container creation requests.
    
    Ensures containers are created sequentially to avoid race conditions
    and Docker API overload when multiple users start containers simultaneously.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one queue exists"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the queue and worker thread"""
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        self._queue = queue.Queue()
        self._worker_thread = None
        self._running = False
        self._stats = {
            'total_requests': 0,
            'successful': 0,
            'failed': 0,
            'in_progress': 0
        }
        self._stats_lock = threading.Lock()
        self._initialized = True
        
        logger.info("ContainerQueue initialized")
    
    def start(self):
        """Start the worker thread to process queue"""
        if self._running:
            logger.warning("ContainerQueue already running")
            return
        
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="ContainerQueueWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("ContainerQueue worker thread started")
    
    def stop(self):
        """Stop the worker thread"""
        if not self._running:
            return
        
        self._running = False
        # Add a sentinel value to wake up the worker
        self._queue.put(None)
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        
        logger.info("ContainerQueue worker thread stopped")
    
    def enqueue(self, request: ContainerCreationRequest) -> str:
        """
        Add a container creation request to the queue
        
        Args:
            request: ContainerCreationRequest object
            
        Returns:
            Request ID for tracking
        """
        with self._stats_lock:
            self._stats['total_requests'] += 1
        
        self._queue.put(request)
        queue_size = self._queue.qsize()
        
        logger.info(
            f"Enqueued container creation request: {request.request_id} "
            f"(queue size: {queue_size})"
        )
        
        return request.request_id
    
    def _process_queue(self):
        """Worker thread function to process container creation requests"""
        logger.info("Container queue worker started processing")
        
        while self._running:
            try:
                # Wait for a request with timeout to allow checking _running flag
                request = self._queue.get(timeout=1)
                
                # Sentinel value for shutdown
                if request is None:
                    break
                
                # Update stats
                with self._stats_lock:
                    self._stats['in_progress'] += 1
                
                logger.info(f"Processing container creation request: {request.request_id}")
                
                try:
                    # Import here to avoid circular dependencies
                    from app.services.docker_manager import DockerManager
                    
                    # Create the container
                    docker_manager = DockerManager()
                    container = docker_manager.create_container(
                        user_id=request.user_id,
                        session_id=request.session_id,
                        username=request.username,
                        desktop_type=request.desktop_type,
                        desktop_image_id=request.desktop_image_id
                    )
                    
                    # Update stats
                    with self._stats_lock:
                        self._stats['successful'] += 1
                        self._stats['in_progress'] -= 1
                    
                    logger.info(
                        f"Successfully created container for request: {request.request_id} "
                        f"(container_id: {container.id if container else 'unknown'})"
                    )
                    
                    # Call success callback if provided
                    if request.callback:
                        try:
                            request.callback(container)
                        except Exception as e:
                            logger.error(f"Error in success callback: {e}")
                
                except Exception as e:
                    # Update stats
                    with self._stats_lock:
                        self._stats['failed'] += 1
                        self._stats['in_progress'] -= 1
                    
                    logger.error(
                        f"Failed to create container for request: {request.request_id} - {str(e)}",
                        exc_info=True
                    )
                    
                    # Call error callback if provided
                    if request.error_callback:
                        try:
                            request.error_callback(e)
                        except Exception as callback_error:
                            logger.error(f"Error in error callback: {callback_error}")
                
                finally:
                    # Mark task as done
                    self._queue.task_done()
                    
            except queue.Empty:
                # Timeout occurred, continue loop to check _running flag
                continue
            except Exception as e:
                logger.error(f"Unexpected error in queue worker: {e}", exc_info=True)
        
        logger.info("Container queue worker stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics
        
        Returns:
            Dictionary with queue statistics
        """
        with self._stats_lock:
            return {
                **self._stats,
                'queue_size': self._queue.qsize(),
                'worker_alive': self._worker_thread.is_alive() if self._worker_thread else False,
                'running': self._running
            }
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()
    
    def is_running(self) -> bool:
        """Check if worker thread is running"""
        return self._running and (self._worker_thread.is_alive() if self._worker_thread else False)


# Global instance
_container_queue = None


def get_container_queue() -> ContainerQueue:
    """Get the global container queue instance"""
    global _container_queue
    if _container_queue is None:
        _container_queue = ContainerQueue()
        # Auto-start the queue
        if not _container_queue.is_running():
            _container_queue.start()
    return _container_queue
