from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
import os
import logging
from utils.gmail_api import init_gmail_service, get_user_email
from utils.email_utils import sync_emails
from routes.email_routes import register_routes
from routes.ai_routes import register_ai_routes
from routes.auth_routes import auth_bp
import atexit

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://127.0.0.1:5000", "http://localhost:8080"],
        "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Credentials", "Access-Control-Allow-Origin"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "send_wildcard": False,
        "max_age": 86400
    }
})

app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/email_client")
mongo = PyMongo(app)

# Create compound index on user_email and id
with app.app_context():
    mongo.db.emails.create_index([("user_email", 1), ("id", 1)])

# Register routes
register_routes(app, mongo)
register_ai_routes(app, mongo)

# Initialize auth routes with mongo instance
from routes.auth_routes import init_auth
init_auth(mongo)
app.register_blueprint(auth_bp, url_prefix='/api/auth')

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
    app.run(debug=False)