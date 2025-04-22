from flask import Blueprint, jsonify, request
from functools import wraps
import secrets
from utils.gmail_api import init_gmail_service, get_user_email
import os
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# In-memory token storage
tokens = {}  # Format: {token: {'email': user_email, 'service': gmail_service}}
mongo = None

def init_auth(mongo_instance):
    global mongo
    mongo = mongo_instance

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Authorization header is required'}), 401

        # Remove 'Bearer ' if present
        token = auth_header.replace('Bearer ', '')
        
        if token not in tokens:
            return jsonify({'error': 'Invalid token'}), 401

        # Add user data to request context
        request.user_email = tokens[token]['email']
        request.gmail_service = tokens[token]['service']
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        # Initialize Gmail service
        client_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client_secret.json')
        service = init_gmail_service(client_file, api_name='gmail', 
                                    api_version='v1', 
                                    scopes=['https://mail.google.com/'])
        
        if not service:
            return jsonify({'error': 'Gmail authentication failed'}), 401

        # Get user's email
        email = get_user_email(service)
        if not email:
            return jsonify({'error': 'Could not get user email'}), 401

        # Generate token
        token = secrets.token_urlsafe(32)
        
        # Store user data
        tokens[token] = {
            'email': email,
            'service': service
        }

        # Sync emails after successful login
        try:
            from utils.email_utils import sync_emails
            if mongo:
                sync_emails(service, email, mongo)
            else:
                logger.error("MongoDB instance not initialized")
        except Exception as e:
            logger.error(f"Error during initial email sync: {str(e)}")
            # Don't fail the login if sync fails
            pass

        return jsonify({
            'token': token,
            'email': email
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.replace('Bearer ', '')
        
        # Remove token
        if token in tokens:
            tokens.pop(token)
            return jsonify({'message': 'Logged out successfully'})
        
        return jsonify({'error': 'Token not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500
