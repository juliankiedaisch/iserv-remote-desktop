from app import db
from datetime import datetime, timezone

class DesktopType(db.Model):
    """Store available desktop types/images"""
    __tablename__ = 'desktop_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)  # e.g., "VS Code", "Ubuntu Desktop"
    docker_image = db.Column(db.String(256), nullable=False)  # e.g., "kasmweb/vs-code:1.16.0"
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(10), nullable=True)  # Emoji icon
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    assignments = db.relationship('DesktopAssignment', backref='desktop_type', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'docker_image': self.docker_image,
            'description': self.description,
            'icon': self.icon,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DesktopAssignment(db.Model):
    """Store which users/groups can access which desktop types"""
    __tablename__ = 'desktop_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    desktop_type_id = db.Column(db.Integer, db.ForeignKey('desktop_types.id'), nullable=False)
    
    # Either group_name OR user_id should be set (not both)
    group_name = db.Column(db.String(128), nullable=True)  # e.g., "lehrende", "lernende"
    user_id = db.Column(db.String(128), nullable=True)  # Specific user UUID
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'desktop_type_id': self.desktop_type_id,
            'group_name': self.group_name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def check_access(cls, desktop_type_id, user_id, user_groups):
        """
        Check if user has access to a desktop type.
        
        Args:
            desktop_type_id: ID of desktop type
            user_id: User's UUID
            user_groups: List of group names user belongs to
            
        Returns:
            Boolean indicating access permission
        """
        # Check for direct user assignment
        user_assignment = cls.query.filter_by(
            desktop_type_id=desktop_type_id,
            user_id=user_id
        ).first()
        
        if user_assignment:
            return True
        
        # Check for group assignment
        if user_groups:
            group_assignment = cls.query.filter(
                cls.desktop_type_id == desktop_type_id,
                cls.group_name.in_(user_groups)
            ).first()
            
            if group_assignment:
                return True
        
        # Check if no assignments exist (open to all)
        assignment_count = cls.query.filter_by(desktop_type_id=desktop_type_id).count()
        return assignment_count == 0
