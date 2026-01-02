#!/usr/bin/env python3
"""
Fix existing containers by setting their desktop_image_id based on desktop_type
"""
import sys
import os

# Change to backend directory
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Add backend directory to path
sys.path.insert(0, os.getcwd())

from app import create_app, db
from app.models.containers import Container
from app.models.desktop_assignments import DesktopImage

def fix_container_desktop_image_ids():
    """Update existing containers to set desktop_image_id"""
    app = create_app()
    
    with app.app_context():
        # Get all containers without desktop_image_id
        containers = Container.query.filter_by(desktop_image_id=None).all()
        
        print(f"Found {len(containers)} containers without desktop_image_id")
        
        fixed_count = 0
        for container in containers:
            if container.desktop_type:
                # Find matching desktop image
                desktop_image = DesktopImage.query.filter_by(name=container.desktop_type).first()
                
                if desktop_image:
                    container.desktop_image_id = desktop_image.id
                    fixed_count += 1
                    print(f"Fixed container {container.container_name}: {container.desktop_type} -> desktop_image_id={desktop_image.id}")
                else:
                    print(f"WARNING: No desktop image found for type '{container.desktop_type}' (container: {container.container_name})")
            else:
                print(f"WARNING: Container {container.container_name} has no desktop_type")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\nSuccessfully fixed {fixed_count} containers")
        else:
            print("\nNo containers needed fixing")

if __name__ == '__main__':
    fix_container_desktop_image_ids()
