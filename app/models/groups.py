from app import db
from datetime import datetime, timezone


class Group(db.Model):
    """Group model for user communities - synced from OAuth provider"""
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    external_id = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Many-to-many relationship with users
    members = db.relationship('User', secondary='user_groups', back_populates='groups')

    
    def __repr__(self):
        return f'<Group {self.name} ({self.external_id})>'
    
    def to_dict(self, include_members=False):
        """
        Convert group to dictionary
        
        Args:
            include_members: Include list of member users
            include_projects: Include list of collaborative projects accessible via permissions
        """
        data = {
            'id': self.id,
            'name': self.name,
            'external_id': self.external_id,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        }
        
        if include_members:
            data['members'] = [{
                'id': member.id,
                'username': member.username
            } for member in self.members]
            data['member_count'] = len(self.members)
        
        return data
    
    @classmethod
    def get_or_create(cls, external_id, name, description=None):
        """Get existing group or create new one based on external ID with proper locking"""
        group = cls.query.filter_by(external_id=external_id).with_for_update().first()
        
        if not group:
            group = cls(
                external_id=external_id,
                name=name,
                description=description
            )
            db.session.add(group)
            db.session.flush()
            
        return group
    
    def has_member(self, user):
        """Check if user is a member of this group"""
        return user in self.members
 
    
    def get_members_count(self):
        """Get number of members in this group"""
        return len(self.members)
 