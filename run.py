import os
if __name__ == '__main__':
    import dotenv
    dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import create_app, db
from sqlalchemy import inspect, text

app = create_app(os.environ["DEBUG"])

def run_migrations():
  pass
# Create tables before the first request (Flask 2.0+ compatible approach)
with app.app_context():
    db.create_all()
    
# Run migrations
run_migrations()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5006 , debug=True)