from app import db
from datetime import datetime, timezone

class DesktopImage(db.Model):
    """Store available desktop images - managed by ADMIN only"""
    __tablename__ = 'desktop_images'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)  # e.g., "VS Code", "Ubuntu Desktop"
    docker_image = db.Column(db.String(256), nullable=False)  # e.g., "kasmweb/vs-code:1.16.0"
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(255), nullable=True)  # Emoji icon or image URL path
    enabled = db.Column(db.Boolean, default=True)
    
    # Metadata
    created_by = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=True)  # Admin who created it
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    assignments = db.relationship('DesktopAssignment', backref='desktop_image', cascade='all, delete-orphan')
    containers = db.relationship('Container', backref='desktop_image_ref', foreign_keys='Container.desktop_image_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'docker_image': self.docker_image,
            'description': self.description,
            'icon': self.icon,
            'enabled': self.enabled,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class DesktopAssignment(db.Model):
    """Store assignments of desktop images to users/groups - created by TEACHER"""
    __tablename__ = 'desktop_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    desktop_image_id = db.Column(db.Integer, db.ForeignKey('desktop_images.id'), nullable=False)
    
    # Target: Either group_id OR user_id should be set (not both)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=True)  # Specific user
    
    # Folder assignments (optional)
    # Path relative to container's /home/kasm-user/public/ directory
    assignment_folder_path = db.Column(db.String(512), nullable=True)  # e.g., "assignments/math101"
    assignment_folder_name = db.Column(db.String(128), nullable=True)  # Display name, e.g., "Math 101 Assignment"
    
    # Assignment metadata
    created_by = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False)  # Teacher who created assignment
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    group = db.relationship('Group', backref='desktop_assignments')
    assigned_user = db.relationship('User', foreign_keys=[user_id], backref='desktop_assignments')
    teacher = db.relationship('User', foreign_keys=[created_by], backref='created_assignments')
    
    def to_dict(self, include_relations=False):
        data = {
            'id': self.id,
            'desktop_image_id': self.desktop_image_id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'assignment_folder_path': self.assignment_folder_path,
            'assignment_folder_name': self.assignment_folder_name,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_relations:
            if self.desktop_image:
                data['desktop_image'] = self.desktop_image.to_dict()
            if self.group:
                data['group'] = {'id': self.group.id, 'name': self.group.name}
            if self.assigned_user:
                data['assigned_user'] = {'id': self.assigned_user.id, 'username': self.assigned_user.username}
            if self.teacher:
                data['teacher'] = {'id': self.teacher.id, 'username': self.teacher.username}
        
        return data
    
    @classmethod
    def check_access(cls, desktop_image_id, user_id, user_group_ids=None):
        """
        Check if user has access to a desktop image.
        
        Args:
            desktop_image_id: ID of desktop image
            user_id: User's UUID
            user_group_ids: List of group IDs (integers) or group names/external_ids (strings) user belongs to
            
        Returns:
            Tuple of (has_access: bool, assignment: DesktopAssignment or None)
        """
        # Check for direct user assignment
        user_assignment = cls.query.filter_by(
            desktop_image_id=desktop_image_id,
            user_id=user_id
        ).first()
        
        if user_assignment:
            return True, user_assignment
        
        # Check for group assignment
        if user_group_ids:
            # Check if we have integer IDs or string names
            if user_group_ids and isinstance(user_group_ids[0], str):
                # We have group names/external_ids, need to join with groups table
                from app.models.groups import Group
                group_assignment = cls.query.join(
                    Group, cls.group_id == Group.id
                ).filter(
                    cls.desktop_image_id == desktop_image_id,
                    Group.external_id.in_(user_group_ids)
                ).first()
            else:
                # We have integer group IDs
                group_assignment = cls.query.filter(
                    cls.desktop_image_id == desktop_image_id,
                    cls.group_id.in_(user_group_ids)
                ).first()
            
            if group_assignment:
                return True, group_assignment
        
        # No assignment found - user does not have access
        return False, None
    
    @classmethod
    def get_user_assignments(cls, user_id, user_group_ids=None):
        """
        Get all desktop images assigned to a user (directly or via groups).
        
        Args:
            user_id: User's UUID
            user_group_ids: List of group IDs user belongs to
            
        Returns:
            List of DesktopAssignment objects
        """
        from sqlalchemy import or_
        
        query = cls.query.filter(
            or_(
                cls.user_id == user_id,
                cls.group_id.in_(user_group_ids) if user_group_ids else False
            )
        )
        
        return query.all()
    
    @classmethod
    def get_by_teacher(cls, teacher_id):
        """
        Get all assignments created by a specific teacher.
        
        Args:
            teacher_id: Teacher's user ID
            
        Returns:
            List of DesktopAssignment objects
        """
        return cls.query.filter_by(created_by=teacher_id).all()
