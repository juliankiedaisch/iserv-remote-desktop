#!/usr/bin/env python3
"""
Update existing containers' proxy_path to replace periods with dashes
for DNS subdomain compatibility
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.containers import Container

app = create_app()

with app.app_context():
    # Get all containers
    containers = Container.query.all()
    
    print(f"Found {len(containers)} containers")
    
    updated = 0
    for container in containers:
        old_proxy_path = container.proxy_path
        
        if old_proxy_path and '.' in old_proxy_path:
            # Replace periods with dashes
            new_proxy_path = old_proxy_path.replace('.', '-')
            
            print(f"\nUpdating container: {container.container_name}")
            print(f"  Old proxy_path: {old_proxy_path}")
            print(f"  New proxy_path: {new_proxy_path}")
            
            container.proxy_path = new_proxy_path
            updated += 1
    
    if updated > 0:
        db.session.commit()
        print(f"\n✅ Updated {updated} container(s)")
        print("\nYou can now access containers at:")
        for container in containers:
            if container.proxy_path:
                print(f"  https://{container.proxy_path}.desktop.hub.mdg-hamburg.de/desktop/{container.proxy_path}")
    else:
        print("\n✅ No containers needed updating")
