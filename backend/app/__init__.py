from flask import Flask, app
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sock import Sock
import os
from urllib.parse import urlparse


# Initialize Flask extensions
db = SQLAlchemy()
oauth = OAuth()
sock = Sock()
socketio = None  # Will be initialized in create_app


def create_app(debug=False):
    global socketio
    app = Flask(__name__)
    # Configure the app based on environment
    if debug:
        app.config.from_object('app.config.DevelopmentConfig')
    else:
        app.config.from_object('app.config.ProductionConfig')
    # Add or update in your app's configuration
    app.config['SECRET_KEY'] = '9Hn8Nw2MvqKUL7o4JbSFOyzpgI_suZ81av0P5J1bbzgak'  # Use a strong, random key
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_COOKIE_DOMAIN'] = f'.{urlparse(app.config["FRONTEND_URL"]).hostname}'
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_PATH'] = '/'
    
    # Important: Set the correct server name if using subdomain session cookies
    app.config['SERVER_NAME'] = urlparse(app.config["FRONTEND_URL"]).hostname  # Adjust to your domain
    #app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['APPLICATION_ROOT'] = '/'
    
    # Fix for proxied requests
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_port=1, x_prefix=1)


    
    # Enable CORS for both Flask routes and WebSocket
    CORS(app, supports_credentials=True, origins=[app.config["FRONTEND_URL"]])
    
    
    # Initialize extensions with app
    db.init_app(app)
    oauth.init_app(app)
    sock.init_app(app)
    
    # Initialize Socket.IO for real-time updates
    from app.routes.websocket_routes import init_socketio
    # Assign to global socketio variable so it can be imported by run.py
    socketio = init_socketio(app)
    globals()['socketio'] = socketio
    
    # Register OAuth provider
    oauth.register(
        name='oauth_provider',
        client_id=app.config['OAUTH_CLIENT_ID'],
        client_secret=app.config['OAUTH_CLIENT_SECRET'],
        authorize_url=app.config['OAUTH_AUTHORIZE_URL'],
        access_token_url=app.config['OAUTH_TOKEN_URL'],
        userinfo_endpoint=app.config['OAUTH_USERINFO_URL'],
        jwks_uri=app.config['OAUTH_JWKS_URI'],
        client_kwargs={'scope': 'openid profile uuid email groups', 'response_type': 'code', 'state_in_authorization_response': True},
        redirect_uri=app.config['OAUTH_REDIRECT_URI'],
        token_endpoint_auth_method='client_secret_post',
        
    )
    print(app.config['OAUTH_REDIRECT_URI'])
    # Register blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.container_routes import container_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.proxy_routes import proxy_bp
    from app.routes.debug_routes import debug_bp
    from app.routes.apache_api_routes import apache_api_bp
    from app.routes.desktop_admin_routes import desktop_admin_bp
    from app.routes.teacher_routes import teacher_bp
    from app.routes.theme_routes import theme_routes
    from app.routes.file_routes import file_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(container_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')
    app.register_blueprint(proxy_bp, url_prefix='/api')
    app.register_blueprint(debug_bp, url_prefix='/api')
    app.register_blueprint(apache_api_bp)
    app.register_blueprint(desktop_admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(theme_routes)
    app.register_blueprint(file_bp, url_prefix='/api')

    return app