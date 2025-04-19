from flask import request, jsonify
import logging
from utils.email_utils import process_new_emails, store_email_in_db
from utils.gmail_api import get_email_messages, get_user_email

logger = logging.getLogger(__name__)

def register_routes(app, gmail_service, mongo):
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"})

    @app.route("/api/fetch_emails", methods=["GET"])
    def fetch_emails():
        BATCH_SIZE = 5
        user_email = get_user_email(gmail_service)
        if not user_email:
            logger.error("Failed to get user email from Gmail API")
            return jsonify({"error": "Could not authenticate user"}), 401

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
                    batch_new_emails = process_new_emails(new_ids, user_email, gmail_service, mongo)
                    all_emails.extend(batch_new_emails)
                break
                
            # If no existing emails found, process all IDs in this batch
            logger.info(f"No cached emails found in batch, processing all {len(batch_ids)} messages")
            batch_new_emails = process_new_emails(batch_ids, user_email, gmail_service, mongo)
            all_emails.extend(batch_new_emails)
            
            # If this was the last batch, no need to continue
            if i + BATCH_SIZE >= len(message_ids):
                logger.info("Reached last batch, stopping")
                break
        
        # Sort all emails by date and time
        all_emails.sort(key=lambda x: (x['date'], x['time']), reverse=True)
        logger.info(f"Returning {len(all_emails)} total emails")
        return jsonify(all_emails)
