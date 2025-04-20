from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
import os
import logging
from utils.gmail_api import init_gmail_service, get_user_email
from utils.email_utils import sync_emails
from routes.email_routes import register_routes
import atexit

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://127.0.0.1:5000", "http://localhost:8080"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/email_client")
mongo = PyMongo(app)

# Create compound index on user_email and id
with app.app_context():
    mongo.db.emails.create_index([("user_email", 1), ("id", 1)])

client_file = os.path.join(os.path.dirname(__file__), 'client_secret.json')
gmail_service = init_gmail_service(client_file, api_name='gmail', api_version='v1', scopes=['https://mail.google.com/'])

# Sync emails after initializing Gmail service
with app.app_context():
    user_email = get_user_email(gmail_service)
    if user_email:
        logger.info(f"Starting initial email sync for {user_email}")
        sync_emails(gmail_service, user_email, mongo)
    else:
        logger.error("Failed to get user email, skipping initial sync")

# Register routes
register_routes(app, gmail_service, mongo)

def cleanup_resources():
    # Clean up database connections
    mongo.cx.close()
    
    # Clean up semaphores
    try:
        import multiprocessing as mp
        if hasattr(mp, '_resource_tracker'):
            # Force the resource tracker to clean up any remaining semaphores
            mp._resource_tracker._resource_tracker._join_process()
    except Exception as e:
        logger.error(f"Error cleaning up semaphores: {e}")

atexit.register(cleanup_resources)

if __name__ == "__main__":
    app.run(debug=True)