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
                 assignment_id: Optional[int] = None,
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
            assignment_id: ID of the assignment this container belongs to
            callback: Function to call on success with container as argument
            error_callback: Function to call on error with exception as argument
        """
        self.user_id = user_id
        self.session_id = session_id
        self.username = username
        self.desktop_type = desktop_type
        self.desktop_image_id = desktop_image_id
        self.assignment_id = assignment_id
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
        self._app = None  # Store Flask app instance for worker thread context
        self._stats = {
            'total_requests': 0,
            'successful': 0,
            'failed': 0,
            'in_progress': 0
        }
        self._stats_lock = threading.Lock()
        self._initialized = True
        
        logger.info("ContainerQueue initialized")
    
    def start(self, app=None):
        """
        Start the worker thread to process queue
        
        Args:
            app: Flask application instance (required for worker thread context)
        """
        logger.info(f"start() called - current state: running={self._running}, thread_alive={self._worker_thread.is_alive() if self._worker_thread else 'None'}")
        
        if self._running:
            if self._worker_thread and self._worker_thread.is_alive():
                logger.warning("ContainerQueue already running with live worker thread")
                return
            else:
                logger.warning("Queue marked as running but worker thread is dead! Resetting...")
                self._running = False
        
        # Store Flask app for worker thread context
        if app:
            self._app = app
            logger.info(f"ContainerQueue: Flask app provided: {app}")
        elif not self._app:
            # Try to get current app if available
            try:
                self._app = current_app._get_current_object()
                logger.info(f"ContainerQueue: Got Flask app from context: {self._app}")
            except RuntimeError as e:
                logger.error(f"No Flask app context available: {e}. Queue may not work properly.")
                # Don't start without an app
                return
        else:
            logger.info(f"ContainerQueue: Using existing Flask app: {self._app}")
        
        if not self._app:
            logger.error("Cannot start queue without Flask app!")
            return
        
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="ContainerQueueWorker",
            daemon=True
        )
        
        try:
            self._worker_thread.start()
            logger.info(f"ContainerQueue worker thread started (thread alive: {self._worker_thread.is_alive()})")
            # Give thread a moment to start
            import time
            time.sleep(0.1)
            if not self._worker_thread.is_alive():
                logger.error("Worker thread died immediately after starting!")
                self._running = False
        except Exception as e:
            logger.error(f"Failed to start worker thread: {e}", exc_info=True)
            self._running = False
    
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
        logger.info(f"ContainerQueue.enqueue called for user: {request.username}, desktop: {request.desktop_type}")
        logger.info(f"ContainerQueue state - running: {self._running}, worker alive: {self._worker_thread.is_alive() if self._worker_thread else False}")
        
        with self._stats_lock:
            self._stats['total_requests'] += 1
            queue_size = self._queue.qsize() + self._stats['in_progress']
        
        self._queue.put(request)
        logger.info(f"Request added to queue. Queue size now: {self._queue.qsize()}")
        
        logger.info(
            f"Enqueued container creation request: {request.request_id} "
            f"(queue position: {queue_size})"
        )
        
        return request.request_id
    
    def _process_queue(self):
        """Worker thread function to process container creation requests"""
        try:
            logger.info("=" * 60)
            logger.info("Container queue worker started processing")
            logger.info(f"Worker thread ID: {threading.current_thread().ident}")
            logger.info(f"Worker thread name: {threading.current_thread().name}")
            
            # Check if we have a Flask app for context
            if not self._app:
                logger.error("No Flask app available for worker thread. Cannot process queue.")
                self._running = False
                return
            
            logger.info(f"Flask app available: {self._app}")
            logger.info(f"Queue running flag: {self._running}")
            logger.info("=" * 60)
            
            while self._running:
                try:
                    #logger.debug(f"Waiting for request... (queue size: {self._queue.qsize()})")
                    
                    # Wait for a request with timeout to allow checking _running flag
                    request = self._queue.get(timeout=1)
                    
                    logger.info(f"Got request from queue: {request}")
                    
                    # Sentinel value for shutdown
                    if request is None:
                        logger.info("Received shutdown sentinel, stopping worker")
                        break
                    
                    # Update stats
                    with self._stats_lock:
                        self._stats['in_progress'] += 1
                    
                    logger.info(f"Processing container creation request: {request.request_id}")
                    
                    # Process the request within Flask app context
                    logger.info("Entering Flask app context...")
                    with self._app.app_context():
                        logger.info("Inside Flask app context")
                        try:
                            # Import here to avoid circular dependencies
                            logger.info("Importing DockerManager...")
                            from app.services.docker_manager import DockerManager
                            
                            # Create the container
                            logger.info(f"Creating DockerManager instance...")
                            docker_manager = DockerManager()
                            logger.info(f"Calling create_container for user {request.username}...")
                            container = docker_manager.create_container(
                                user_id=request.user_id,
                                session_id=request.session_id,
                                username=request.username,
                                desktop_type=request.desktop_type,
                                desktop_image_id=request.desktop_image_id,
                                assignment_id=request.assignment_id
                            )
                            logger.info(f"Container created successfully: {container.id if container else 'None'}")
                            
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
                            
                            logger.error("=" * 60)
                            logger.error(
                                f"Failed to create container for request: {request.request_id} - {str(e)}",
                                exc_info=True
                            )
                            logger.error(f"Error type: {type(e).__name__}")
                            logger.error("=" * 60)
                            
                            # Call error callback if provided
                            if request.error_callback:
                                try:
                                    request.error_callback(e)
                                except Exception as callback_error:
                                    logger.error(f"Error in error callback: {callback_error}")
                    
                    # Mark task as done (outside app context)
                    logger.info(f"Marking task as done for request: {request.request_id}")
                    self._queue.task_done()
                    logger.info(f"Task marked as done. Queue size now: {self._queue.qsize()}")
                        
                except queue.Empty:
                    # Timeout occurred, continue loop to check _running flag
                    # logger.debug("Queue timeout (1s) - no requests, continuing...")
                    continue
                except Exception as e:
                    logger.error("=" * 60)
                    logger.error(f"Unexpected error in queue worker: {e}", exc_info=True)
                    logger.error(f"Error type: {type(e).__name__}")
                    logger.error("=" * 60)
                    # Still mark as done to prevent queue blocking
                    try:
                        self._queue.task_done()
                    except:
                        pass
        
            logger.info("=" * 60)
            logger.info("Container queue worker stopped")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"FATAL: Worker thread crashed with uncaught exception: {e}", exc_info=True)
            logger.error("=" * 60)
            self._running = False
            raise
    
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
_container_queue_lock = threading.Lock()


def get_container_queue(app=None) -> ContainerQueue:
    """
    Get the global container queue instance
    
    Args:
        app: Flask application instance (optional, but recommended for first call)
    """
    global _container_queue
    
    logger.info(f"get_container_queue called with app: {app}")
    
    if _container_queue is None:
        logger.info("Creating new ContainerQueue instance (first time)")
        with _container_queue_lock:
            if _container_queue is None:
                _container_queue = ContainerQueue()
                logger.info(f"ContainerQueue instance created, is_running: {_container_queue.is_running()}")
                # Auto-start the queue with app context if available
                if not _container_queue.is_running():
                    logger.info("Auto-starting queue...")
                    _container_queue.start(app)
                    logger.info(f"After start(), is_running: {_container_queue.is_running()}")
                else:
                    logger.warning("Queue already running, skipping auto-start")
    else:
        logger.info(f"Returning existing queue, is_running: {_container_queue.is_running()}")
        # If queue exists but not running, restart it
        if not _container_queue.is_running() and app:
            logger.warning("Queue exists but not running! Attempting to restart...")
            _container_queue.start(app)
    
    return _container_queue

