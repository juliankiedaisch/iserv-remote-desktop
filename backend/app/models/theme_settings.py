from app import db
from datetime import datetime
import json


class ThemeSettings(db.Model):
    __tablename__ = 'theme_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    settings = db.Column(db.Text, nullable=False)  # JSON string of theme settings
    favicon = db.Column(db.Text, nullable=True)  # Base64 encoded favicon or URL
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def theme_dict(self):
        """Parse the settings JSON string to a dictionary."""
        try:
            return json.loads(self.settings)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    @theme_dict.setter
    def theme_dict(self, value):
        """Set the settings from a dictionary."""
        self.settings = json.dumps(value)
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'settings': self.theme_dict,
            'favicon': self.favicon,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_current_theme():
        """Get the current theme settings, or create default if none exists."""
        theme = ThemeSettings.query.first()
        if not theme:
            # Create default theme
            default_theme = {
                'color-primary': '#3e59d1',
                'color-primary-dark': '#303383',
                'color-primary-gradient-start': '#667eea',
                'color-primary-gradient-end': '#764ba2',
                'color-secondary': '#38d352',
                'color-secondary-dark': '#278d31',
                'color-success': '#28a745',
                'color-danger': '#dc3545',
                'color-danger-hover': '#c82333',
                'color-warning': '#ffc107',
                'color-info': '#17a2b8',
                'color-gray': '#6c757d',
                'color-gray-dark': '#5a6268',
                'color-admin-badge': '#aaffad',
                'color-admin-button': '#32469c',
                'color-admin-button-hover': '#2d3c8d',
            }
            theme = ThemeSettings(settings=json.dumps(default_theme))
            db.session.add(theme)
            db.session.commit()
        return theme
