"""
Background scheduler for periodic tasks
"""
import threading
import time
from flask import current_app
from datetime import datetime


class BackgroundScheduler:
    """Simple background task scheduler"""
    
    def __init__(self, app=None):
        self.app = app
        self.tasks = []
        self.running = False
        self.thread = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize scheduler with Flask app"""
        self.app = app
        
        # Register cleanup on app shutdown
        @app.teardown_appcontext
        def shutdown_scheduler(exception=None):
            self.stop()
    
    def add_task(self, func, interval_seconds, name=None):
        """
        Add a periodic task
        
        Args:
            func: Function to call (should accept app context)
            interval_seconds: How often to run the task (in seconds)
            name: Optional name for the task
        """
        task = {
            'func': func,
            'interval': interval_seconds,
            'name': name or func.__name__,
            'last_run': None
        }
        self.tasks.append(task)
        
        # Always print to console for visibility
        print(f"Scheduled task: {task['name']} (every {interval_seconds}s)")
        
        # Log only when app context is available
        if self.app:
            with self.app.app_context():
                current_app.logger.info(f"Scheduled task: {task['name']} (every {interval_seconds}s)")
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            print("Background scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        print(f"Background scheduler started with {len(self.tasks)} tasks")
        # Log only when app context is available
        if self.app:
            with self.app.app_context():
                current_app.logger.info(f"Background scheduler started with {len(self.tasks)} tasks")
    
    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        # Simple print instead of logging to avoid recursion
        print("Background scheduler stopped")
    
    def _run(self):
        """Main scheduler loop"""
        while self.running:
            now = time.time()
            
            for task in self.tasks:
                # Check if it's time to run this task
                if task['last_run'] is None or (now - task['last_run']) >= task['interval']:
                    try:
                        # Run task in app context
                        with self.app.app_context():
                            current_app.logger.debug(f"[Scheduler] Running task: {task['name']}")
                            task['func']()
                            task['last_run'] = now
                    except Exception as e:
                        # Use print to ensure errors are visible even if logging fails
                        print(f"ERROR in scheduled task {task['name']}: {str(e)}")
                        if self.app:
                            with self.app.app_context():
                                current_app.logger.error(
                                    f"Error running scheduled task {task['name']}: {str(e)}",
                                    exc_info=True
                                )
            
            # Sleep for a short time before checking again
            time.sleep(60)  # Check every minute


# Global scheduler instance
scheduler = BackgroundScheduler()


def check_idle_containers():
    """Background task to check and stop idle containers"""
    from app.services.docker_manager import DockerManager
    from flask import current_app
    
    try:
        # Get idle timeout from config (default: 1.5 hours = 90 minutes)
        idle_hours = current_app.config.get('CONTAINER_IDLE_TIMEOUT_HOURS', 1.5)
        
        current_app.logger.info(
            f"[Scheduler] Checking for idle containers (timeout: {idle_hours} hours)"
        )
        
        docker_manager = DockerManager()
        stopped_count = docker_manager.stop_idle_containers(idle_hours=idle_hours)
        
        if stopped_count > 0:
            current_app.logger.info(
                f"[Scheduler] Stopped {stopped_count} idle containers"
            )
        else:
            current_app.logger.debug(
                f"[Scheduler] No idle containers to stop"
            )
    except Exception as e:
        current_app.logger.error(f"[Scheduler] Failed to check idle containers: {str(e)}")


def cleanup_old_containers():
    """Background task to cleanup old stopped containers"""
    from app.services.docker_manager import DockerManager
    from flask import current_app
    
    try:
        docker_manager = DockerManager()
        docker_manager.cleanup_stopped_containers()
    except Exception as e:
        current_app.logger.error(f"[Scheduler] Failed to cleanup containers: {str(e)}")


def sync_database_with_docker():
    """Background task to synchronize database with Docker state"""
    from app.services.docker_manager import DockerManager
    from flask import current_app
    
    try:
        docker_manager = DockerManager()
        stats = docker_manager.sync_database_with_docker()
        
        if 'error' not in stats:
            # Only log if there were changes
            if (stats.get('removed_orphaned', 0) + stats.get('updated_status', 0) + 
                stats.get('cleaned_stuck', 0) + stats.get('normalized_paths', 0) > 0):
                current_app.logger.info(
                    f"[Scheduler] Database sync: {stats.get('removed_orphaned', 0)} orphaned removed, "
                    f"{stats.get('updated_status', 0)} status updated, "
                    f"{stats.get('cleaned_stuck', 0)} stuck cleaned, "
                    f"{stats.get('normalized_paths', 0)} paths normalized"
                )
        else:
            current_app.logger.error(f"[Scheduler] Database sync failed: {stats['error']}")
    except Exception as e:
        current_app.logger.error(f"[Scheduler] Failed to sync database: {str(e)}")

