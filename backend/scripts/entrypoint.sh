#!/bin/bash
set -e

echo "Starting IServ Remote Desktop application..."

# Wait for database to be ready

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h "${POSTGRES_SERVER_NAME:-postgres}" -U "${POSTGRES_USER:-desktop_db_user}" -d "${POSTGRES_DB:-desktop_db}"; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done
echo "PostgreSQL is ready!"


# Run database migrations synchronously
echo "Running database migrations..."
python3 << 'PYTHON_SCRIPT'
import os
from app import create_app, db

app = create_app(os.environ.get("DEBUG", "False") == "True")
with app.app_context():
    db.create_all()
    print("Database tables created successfully")
PYTHON_SCRIPT

# Start the application with gunicorn
# Using gevent worker with gevent-websocket for WebSocket support
# This provides wsgi.websocket in request.environ for WebSocket routes
echo "Starting application server..."
exec gunicorn --bind 0.0.0.0:5006 \
    --workers 4 \
    --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    run:app
