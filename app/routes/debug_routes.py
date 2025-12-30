"""
Flask header inspection route - temporarily add this to see what headers are received
"""

from flask import Blueprint, request, jsonify

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/debug/headers')
def show_headers():
    """Show all headers received by Flask"""
    headers = dict(request.headers)
    return jsonify({
        'headers': headers,
        'environ': {
            'REMOTE_ADDR': request.environ.get('REMOTE_ADDR'),
            'HTTP_X_FORWARDED_FOR': request.environ.get('HTTP_X_FORWARDED_FOR'),
            'HTTP_X_FORWARDED_PROTO': request.environ.get('HTTP_X_FORWARDED_PROTO'),
            'wsgi.url_scheme': request.environ.get('wsgi.url_scheme'),
        },
        'cookies': dict(request.cookies),
        'referer': request.referrer,
        'origin': request.headers.get('Origin'),
    })

# To add this route, import and register this blueprint in app/__init__.py:
# from app.routes.debug_routes import debug_bp
# app.register_blueprint(debug_bp)
