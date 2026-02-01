from flask import Blueprint, jsonify
import os

version_bp = Blueprint('version', __name__)


@version_bp.route('/version', methods=['GET'])
def get_version():
    """
    Get the current version of the backend.
    """
    version_file = os.path.join(os.path.dirname(__file__), '..', '..', 'VERSION')
    
    try:
        with open(version_file, 'r') as f:
            version = f.read().strip()
        return jsonify({'version': version}), 200
    except Exception as e:
        return jsonify({'error': 'Unable to read version', 'version': 'unknown'}), 500
