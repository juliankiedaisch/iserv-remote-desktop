from app import db
from datetime import datetime, timezone
import uuid

def generate_container_id():
    return str(uuid.uuid4())

class Container(db.Model):
    """Store container information for each user session"""
    __tablename__ = 'containers'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_container_id)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(36), db.ForeignKey('oauth_sessions.id'), nullable=False)
    
    # Docker container details
    container_id = db.Column(db.String(128), nullable=True)  # Docker container ID
    container_name = db.Column(db.String(128), nullable=False, unique=True)
    image_name = db.Column(db.String(256), nullable=False)
    
    # Container status
    status = db.Column(db.String(50), nullable=False, default='creating')  # creating, running, stopped, error
    
    # Connection details
    host_port = db.Column(db.Integer, nullable=True)  # Port on host machine
    container_port = db.Column(db.Integer, nullable=False, default=6901)  # Default Kasm VNC port
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    stopped_at = db.Column(db.DateTime, nullable=True)
    last_accessed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='containers')
    session = db.relationship('OAuthSession', backref='containers')
    
    @classmethod
    def get_by_session(cls, session_id):
        """Get active container for a session"""
        return cls.query.filter_by(
            session_id=session_id,
            status='running'
        ).first()
    
    @classmethod
    def get_by_user(cls, user_id):
        """Get all containers for a user"""
        return cls.query.filter_by(user_id=user_id).all()
    
    def to_dict(self):
        """Convert container to dictionary"""
        return {
            'id': self.id,
            'container_id': self.container_id,
            'container_name': self.container_name,
            'status': self.status,
            'host_port': self.host_port,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None
        }
    
    def __repr__(self):
        return f'<Container {self.container_name} ({self.status})>'
