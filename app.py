from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_pymongo import PyMongo
import os
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime

from utils.gmail_api import init_gmail_service, get_email_messages, get_email_message_details

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

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

@app.route("/api/fetch_emails", methods=["GET"])
def fetch_emails():
    BATCH_SIZE = 5
    user_email = request.args.get('user_email')
    if not user_email:
        logger.error("No user_email provided in request")
        return jsonify({"error": "user_email parameter is required"}), 400

    logger.info(f"Fetching emails for user: {user_email}")
    
    # Get latest 20 message IDs from Gmail
    messages = get_email_messages(gmail_service, user_id='me', label_ids=None, folder_name='INBOX', max_results=20)
    message_ids = [msg['id'] for msg in messages]
    
    if not message_ids:
        logger.info("No emails found in inbox")
        return jsonify([])
    
    logger.info(f"Found {len(message_ids)} message IDs to process")
    all_emails = []
    found_existing = False
    
    # Process message IDs in batches
    for i in range(0, len(message_ids), BATCH_SIZE):
        batch_ids = message_ids[i:i + BATCH_SIZE]
        logger.info(f"Processing batch {i//BATCH_SIZE + 1}: {len(batch_ids)} messages")
        
        # Check if these IDs exist in database
        existing_emails = list(mongo.db.emails.find(
            {'user_email': user_email, 'id': {'$in': batch_ids}},
            {'_id': 0}
        ))
        existing_ids = {email['id'] for email in existing_emails}
        
        # If we found any existing emails, add them and stop processing
        if existing_emails:
            logger.info(f"Found {len(existing_emails)} cached emails in batch")
            all_emails.extend(existing_emails)
            found_existing = True
            # Only process new IDs up to this batch
            new_ids = set(batch_ids) - existing_ids
            if new_ids:
                logger.info(f"Processing {len(new_ids)} new emails in current batch")
                batch_new_emails = process_new_emails(new_ids, user_email)
                all_emails.extend(batch_new_emails)
            break
            
        # If no existing emails found, process all IDs in this batch
        logger.info(f"No cached emails found in batch, processing all {len(batch_ids)} messages")
        batch_new_emails = process_new_emails(batch_ids, user_email)
        all_emails.extend(batch_new_emails)
        
        # If this was the last batch, no need to continue
        if i + BATCH_SIZE >= len(message_ids):
            logger.info("Reached last batch, stopping")
            break
    
    # Sort all emails by date and time
    all_emails.sort(key=lambda x: (x['date'], x['time']), reverse=True)
    logger.info(f"Returning {len(all_emails)} total emails")
    return jsonify(all_emails)

def process_new_emails(msg_ids, user_email):
    """Helper function to process new email IDs"""
    logger.info(f"Processing {len(msg_ids)} new emails")
    new_emails = []
    for msg_id in msg_ids:
        try:
            detail = get_email_message_details(gmail_service, msg_id)
            logger.debug(f"Retrieved details for message ID: {msg_id}")
            
            # Parse the date string
            date_str = detail.get('date', '')
            if date_str:
                parsed_date = parsedate_to_datetime(date_str)
                formatted_date = parsed_date.strftime('%Y-%m-%d')
                formatted_time = parsed_date.strftime('%H:%M:%S')
            else:
                formatted_date = ''
                formatted_time = ''

            label = detail.get('label', '')
            label = label.split(', ')

            is_unread = 'UNREAD' in label

            email_info = {
                'id': msg_id,
                'subject': detail.get('subject', ''),
                'sender': detail.get('sender', ''),
                'recipients': detail.get('recipients', []),
                'body': detail.get('body', ''),
                'snippet': detail.get('snippet', ''),
                'has_attachments': detail.get('has_attachments', False),
                'date': formatted_date,
                'time': formatted_time,
                'star': detail.get('star', False),
                'label': label,
                'read': not is_unread,
                'spam': False,
                'phishing': False
            }
            
            # Store new email in database
            store_email_in_db(email_info, user_email)
            new_emails.append(email_info)
        except Exception as e:
            logger.error(f"Error processing message ID {msg_id}: {str(e)}")
            continue
    
    return new_emails

def store_email_in_db(email_info, user_email):
    """Store email info in MongoDB with user reference"""
    try:
        mongo.db.emails.update_one(
            {'id': email_info['id'], 'user_email': user_email},
            {'$set': email_info},
            upsert=True
        )
        logger.debug(f"Stored email {email_info['id']} in database")
        return True
    except Exception as e:
        logger.error(f"Error storing email {email_info['id']}: {str(e)}")
        return False

if __name__ == "__main__":
    app.run(debug=True)