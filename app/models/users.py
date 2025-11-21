from app import db
from datetime import datetime, timezone
import uuid
from flask import current_app

# User-Group association table (many-to-many relationship)
user_groups = db.Table('user_groups',
    db.Column('user_id', db.String(128), db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)


class User(db.Model):
    """Store permanent user data"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(128), primary_key=True)
    username = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    user_data = db.Column(db.JSON, nullable=True)
    
    # Relationships
    sessions = db.relationship('OAuthSession', back_populates='user', cascade='all, delete-orphan')
    
    # Many-to-many relationship with groups
    groups = db.relationship('Group', secondary=user_groups, back_populates='members')

    
    @classmethod
    def get_or_create(cls, user_id, username, email=None, user_data=None):
        """Get existing user or create a new one with proper locking"""
        user = cls.query.filter_by(id=user_id).with_for_update().first()
        
        if not user:
            user = cls(
                id=user_id,
                username=username,
                email=email,
                user_data=user_data
            )
            db.session.add(user)
            db.session.flush()
        else:
            user.username = username
            user.email = email
            user.last_login = datetime.now(timezone.utc)
            if user_data:
                user.user_data = user_data
        
        # Extract role from user_data
        if user_data and 'groups' in user_data:
            role = 'user'
            if type(user_data.get('groups')) == dict:
                groups = [elem["act"] for elem in user_data.get('groups', {}).values()]
            else:
                groups = []
            if current_app.config['ROLE_ADMIN'] in groups:
                role = 'admin'
            elif current_app.config['ROLE_TEACHER'] in groups:
                role = 'teacher'
            else:
                role = 'student'
            user.role = role
        
        return user
    
    # ============================================================
    # ROLE CHECKS
    # ============================================================
    
    @property
    def is_teacher(self):
        """Check if user is a teacher"""
        return self.role == 'teacher'
    
    @property
    def is_admin(self):
        """Check if user is an admin"""
        return self.role == 'admin'
    
    @property
    def is_student(self):
        """Check if user is a student"""
        return self.role == 'student'
    
    # ============================================================
    # SERIALIZATION
    # ============================================================
    
    def to_dict(self):
        """
        Convert user to dictionary
        
        Args:
            include_projects: Include collaborative projects
        
        Returns: Dictionary representation of user
        """
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat(),
            'groups': [group.to_dict() for group in self.groups]
        }
        
        
        return data
    
    def __repr__(self):
        return f'<User {self.username} ({self.id})>'