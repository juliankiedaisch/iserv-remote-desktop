from app import db
from datetime import datetime, timezone, timedelta
import uuid
from app.models.users import User
from app.models.groups import Group

def generate_session_id():
    return str(uuid.uuid4())

class OAuthSession(db.Model):
    """Store temporary OAuth session data"""
    __tablename__ = 'oauth_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_session_id)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False)
    access_token = db.Column(db.Text, nullable=False)    # OAuth access token
    refresh_token = db.Column(db.Text, nullable=True)    # OAuth refresh token
    expires_at = db.Column(db.DateTime, nullable=False)  # Token expiration time
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_accessed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship to user
    user = db.relationship('User', back_populates='sessions')
    
    @classmethod
    def create_session(cls, user_id, username, email, tokens, user_data=None):
        """Create new session and update or create user"""
        
        
        # Ensure timezone-aware expiration handling
        if 'expires_at' in tokens:
            expires_at = datetime.fromtimestamp(tokens.get('expires_at', 0), tz=timezone.utc)
        elif 'expires_in' in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get('expires_in', 60)))
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
            
        if expires_at < datetime.now(timezone.utc):
            raise ValueError("Invalid or expired token")
        
        # First get or create the user
        user = User.get_or_create(user_id, username, email, user_data)
        
        # Create new session
        session = cls(
            user_id=user_id,
            access_token=tokens.get('access_token', ''),
            refresh_token=tokens.get('refresh_token', ''),
            expires_at=expires_at,
            last_accessed=datetime.now(timezone.utc)
        )
        
        # Add session to database
        db.session.add(session)
        db.session.flush()  # Generate ID without committing
        
        # Sync groups from OAuth data
        if user_data:
            cls._sync_groups(user, user_data)
        
        db.session.commit()
        return session
    
    @staticmethod
    def _sync_groups(user, user_data):
        """Sync user groups from OAuth data"""
        from app.models.groups import Group
        
        # Clear existing group associations
        user.groups = []
        
        # Extract groups from user data
        oauth_groups = []
        # Check for groups in standard locations
        if 'groups' in user_data and type(user_data['groups']) == dict:
            raw_groups = [elem for elem in user_data.get('groups', {}).values()]
            for group in raw_groups:
                # Object groups
                oauth_groups.append({
                    'id': group.get('act'),
                    'name': group.get('name', group.get('act', 'Unknown'))
                })
        # Now create/update local groups and link to user
        for oauth_group in oauth_groups:
            # Create or get group
            group = Group.get_or_create(
                external_id=oauth_group['id'],
                name=oauth_group['name']
            )
            # Add user to group
            if group not in user.groups:
                user.groups.append(group)
    
    def to_dict(self):
        """Convert session to dictionary for client"""
        return {
            'session_id': self.id,
            'user': self.user.to_dict(),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat()
        }
    
    def update_tokens(self, new_tokens):
        """Update tokens and recalculate expiration time"""
        # Update the token fields
        if 'access_token' in new_tokens:
            self.access_token = new_tokens['access_token']
        if 'refresh_token' in new_tokens:
            self.refresh_token = new_tokens['refresh_token']
        
        # Calculate new expiration time - always use timezone-aware datetimes
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=12)
        
        # Update last_accessed
        self.last_accessed = datetime.now(timezone.utc)
        
        # Update user data if provided
        if 'userinfo' in new_tokens:
            self.user.user_data = new_tokens['userinfo']
            # Update user groups
            self._sync_groups(self.user, new_tokens['userinfo'])
            
        return self
    
    @classmethod
    def get_by_session_id(cls, session_id):
        return cls.query.filter_by(id=session_id).first()