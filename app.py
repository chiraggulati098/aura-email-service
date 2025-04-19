from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
import os
import logging
from utils.gmail_api import init_gmail_service
from routes.email_routes import register_routes

app = Flask(__name__)
CORS(app)

app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/email_client")
mongo = PyMongo(app)

# Create compound index on user_email and id
with app.app_context():
    mongo.db.emails.create_index([("user_email", 1), ("id", 1)])

client_file = os.path.join(os.path.dirname(__file__), 'client_secret.json')
gmail_service = init_gmail_service(client_file, api_name='gmail', api_version='v1', scopes=['https://mail.google.com/'])

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Register routes
register_routes(app, gmail_service, mongo)

if __name__ == "__main__":
    app.run(debug=True)