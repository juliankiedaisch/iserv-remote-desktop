#!/usr/bin/env python3
"""
Cleanup script for expired containers and sessions

This script can be run as a cron job to periodically clean up:
- Stopped containers older than 1 hour
- Expired sessions
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.services.docker_manager import DockerManager
from app.models.oauth_session import OAuthSession
from datetime import datetime, timezone, timedelta

def cleanup_expired_sessions():
    """Remove expired OAuth sessions"""
    try:
        current_time = datetime.now(timezone.utc)
        expired_sessions = OAuthSession.query.filter(
            OAuthSession.expires_at < current_time
        ).all()
        
        count = 0
        for session in expired_sessions:
            print(f"Removing expired session: {session.id} (user: {session.user.username})")
            db.session.delete(session)
            count += 1
        
        db.session.commit()
        print(f"Removed {count} expired sessions")
        return count
        
    except Exception as e:
        print(f"Error cleaning up sessions: {str(e)}")
        db.session.rollback()
        return 0

def cleanup_containers():
    """Remove stopped containers"""
    try:
        docker_manager = DockerManager()
        docker_manager.cleanup_stopped_containers()
        print("Container cleanup completed")
        
    except Exception as e:
        print(f"Error cleaning up containers: {str(e)}")

def main():
    """Main cleanup function"""
    print(f"Starting cleanup at {datetime.now()}")
    
    # Create Flask app context
    app = create_app(os.environ.get('DEBUG', 'False') == 'True')
    
    with app.app_context():
        # Cleanup expired sessions
        cleanup_expired_sessions()
        
        # Cleanup stopped containers
        cleanup_containers()
    
    print(f"Cleanup completed at {datetime.now()}")

if __name__ == '__main__':
    main()
