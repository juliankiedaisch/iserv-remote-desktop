"""
WebRTC routes for TURN/STUN configuration and signaling
"""

from flask import Blueprint, request, jsonify, current_app
from app.middlewares.auth import require_auth
import os
import hmac
import hashlib
import base64
import time

webrtc_bp = Blueprint('webrtc', __name__)


@webrtc_bp.route('/webrtc/config', methods=['GET'])
@require_auth
def get_webrtc_config(user_dict):
    """
    Get WebRTC configuration including TURN/STUN server credentials
    
    Returns ICE server configuration for WebRTC connections
    """
    try:
        # Check if WebRTC is enabled
        webrtc_enabled = os.environ.get('WEBRTC_ENABLED', 'false').lower() == 'true'
        
        if not webrtc_enabled:
            return jsonify({
                'success': True,
                'enabled': False,
                'ice_servers': []
            })
        
        # Get TURN/STUN configuration from environment
        turn_url = os.environ.get('TURN_SERVER_URL', '')
        stun_url = os.environ.get('STUN_SERVER_URL', '')
        turn_username = os.environ.get('TURN_SERVER_USERNAME', '')
        turn_credential = os.environ.get('TURN_SERVER_CREDENTIAL', '')
        static_auth_secret = os.environ.get('TURN_STATIC_AUTH_SECRET', '')
        
        ice_servers = []
        
        # Add STUN server if configured
        if stun_url:
            ice_servers.append({
                'urls': stun_url
            })
        
        # Add TURN server with authentication
        if turn_url:
            if static_auth_secret:
                # Use REST API authentication with time-limited credentials
                # Generate time-limited credentials using HMAC-SHA1
                # Note: SHA1 is used for compatibility with RFC 5766 TURN REST API
                # Most TURN servers (including coturn) require SHA1 for this purpose
                username = user_dict.get('username', 'user')
                timestamp = int(time.time()) + 86400  # Valid for 24 hours
                turn_username = f"{timestamp}:{username}"
                
                # Generate credential using HMAC-SHA1 (RFC 5766 requirement)
                message = turn_username.encode('utf-8')
                key = static_auth_secret.encode('utf-8')
                turn_credential = base64.b64encode(
                    hmac.new(key, message, hashlib.sha1).digest()
                ).decode('utf-8')
            elif not turn_username or not turn_credential:
                # No authentication configured
                current_app.logger.warning("TURN server configured but no authentication provided")
            
            ice_servers.append({
                'urls': turn_url,
                'username': turn_username,
                'credential': turn_credential
            })
        
        # Get local network CIDR ranges for network detection
        local_cidrs = os.environ.get('LOCAL_NETWORK_CIDR', '192.168.0.0/16,10.0.0.0/8,172.16.0.0/12')
        
        return jsonify({
            'success': True,
            'enabled': True,
            'ice_servers': ice_servers,
            'local_network_cidrs': local_cidrs.split(',')
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get WebRTC config: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@webrtc_bp.route('/webrtc/network/check', methods=['GET'])
@require_auth  
def check_network_location(user_dict):
    """
    Check if client is in local network based on IP address
    
    Returns whether the client is in the local network
    """
    try:
        import ipaddress
        
        # Get client IP from request
        # Check X-Forwarded-For header first (when behind proxy)
        client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if not client_ip:
            client_ip = request.headers.get('X-Real-IP', '')
        if not client_ip:
            client_ip = request.remote_addr
        
        # Get local network CIDR ranges
        local_cidrs_str = os.environ.get('LOCAL_NETWORK_CIDR', '192.168.0.0/16,10.0.0.0/8,172.16.0.0/12')
        local_cidrs = [cidr.strip() for cidr in local_cidrs_str.split(',')]
        
        # Check if IP is in any local network range
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            is_local = False
            
            for cidr in local_cidrs:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    if client_ip_obj in network:
                        is_local = True
                        break
                except ValueError:
                    current_app.logger.warning(f"Invalid CIDR notation: {cidr}")
                    continue
            
            return jsonify({
                'success': True,
                'is_local_network': is_local,
                'client_ip': str(client_ip),
                'local_networks': local_cidrs
            })
            
        except ValueError:
            # Invalid IP address
            return jsonify({
                'success': False,
                'error': f'Invalid IP address: {client_ip}'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Failed to check network location: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
