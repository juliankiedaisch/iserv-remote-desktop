#!/usr/bin/env python3
"""
Check what URL Flask would generate for the container
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models.containers import Container

app = create_app()

with app.app_context():
    containers = Container.query.all()
    
    if not containers:
        print("No containers in database")
    else:
        for c in containers:
            print(f"Container: {c.container_name}")
            print(f"  proxy_path: {c.proxy_path}")
            print(f"  status: {c.status}")
            print(f"  port: {c.port}")
            
            # Generate URL
            from app.services.docker_manager import DockerManager
            dm = DockerManager()
            url = dm.get_container_url(c)
            print(f"  URL: {url}")
            print()
