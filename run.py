# Monkey patch FIRST, before any other imports (fixes gevent + threading conflicts)
from gevent import monkey
monkey.patch_all()

import os
if __name__ == '__main__':
    import dotenv
    dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import create_app, db
from sqlalchemy import inspect, text

app = create_app(os.environ["DEBUG"])

def run_migrations():
    """Run SQL migration files from the migrations directory
    
    NOTE: Migration files should only contain DDL statements (CREATE, ALTER, DROP).
    Migrations are executed in sorted order by filename.
    Each migration should be idempotent (safe to run multiple times).
    """
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    
    if not os.path.exists(migrations_dir):
        return
    
    # Get all SQL migration files sorted by name
    migration_files = sorted([
        f for f in os.listdir(migrations_dir)
        if f.endswith('.sql')
    ])
    
    if not migration_files:
        return
    
    for migration_file in migration_files:
        migration_path = os.path.join(migrations_dir, migration_file)
        try:
            with open(migration_path, 'r') as f:
                sql = f.read()
            
            # Execute the migration SQL
            db.session.execute(text(sql))
            db.session.commit()
            print(f"✓ Executed migration: {migration_file}")
        except Exception as e:
            print(f"✗ Migration {migration_file} failed: {str(e)}")
            # Rollback the failed migration to maintain database consistency
            db.session.rollback()

# Create tables before the first request (Flask 2.0+ compatible approach)
with app.app_context():
    db.create_all()
    
    # Run migrations after creating tables
    run_migrations()

if __name__ == '__main__':
    # Use gevent server for WebSocket support in development
    # flask-sock provides WebSocket support at the Flask application level
    from gevent import pywsgi
    
    server = pywsgi.WSGIServer(
        ('0.0.0.0', 5020),
        app
    )
    
    print("=" * 70)
    print("Starting IServ Remote Desktop with WebSocket support")
    print("Server: gevent + flask-sock (development mode)")
    print("Address: http://0.0.0.0:5020")
    print("WebSocket support: ENABLED (via flask-sock)")
    print("=" * 70)
    
    server.serve_forever()