from utils.gmail_api import get_email_messages, get_email_message_details
from utils.phishing_utils import predict_phishing
from utils.spam_utils import predict_spam
import logging
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

def sync_emails(gmail_service, user_email, mongo):
    """
    Sync emails from Gmail to MongoDB using exponential batch sizes.
    Returns when it finds emails that are already in the database or no more emails exist.
    Collects all new message IDs before processing them at once.
    """
    logger.info("Starting email sync")
    batch_size = 2
    new_message_ids = set()
    
    while True:
        logger.info(f"Fetching batch of {batch_size} emails")
        messages = get_email_messages(gmail_service, max_results=batch_size)
        
        # No more emails to fetch
        if len(messages) < batch_size:
            logger.info(f"Found {len(messages)} emails, less than batch size {batch_size}. Adding to final batch.")
            if messages:
                message_ids = [msg['id'] for msg in messages]
                new_message_ids.update(message_ids)
            break
            
        message_ids = [msg['id'] for msg in messages]
        
        # Check which emails already exist in database
        existing_emails = list(mongo.db.emails.find(
            {'user_email': user_email, 'id': {'$in': message_ids}},
            {'id': 1}
        ))
        existing_ids = {email['id'] for email in existing_emails}
        
        # If we found any existing emails, we can stop after adding new ones to our set
        if existing_ids:
            logger.info(f"Found {len(existing_ids)} existing emails, adding remaining new ones to final batch")
            new_ids = set(message_ids) - existing_ids
            new_message_ids.update(new_ids)
            break
        
        # No existing emails found, add all IDs from this batch
        logger.info(f"Adding {len(message_ids)} new email IDs to batch")
        new_message_ids.update(message_ids)
        
        # Double the batch size for next iteration
        batch_size *= 2
    
    # Process all new emails at once
    if new_message_ids:
        logger.info(f"Processing all {len(new_message_ids)} new emails")
        processed_emails = process_new_emails(list(new_message_ids), user_email, gmail_service, mongo)
        processed_count = len(processed_emails)
    else:
        logger.info("No new emails to process")
        processed_count = 0
    
    logger.info(f"Sync completed. Processed {processed_count} new emails")
    return processed_count

def process_new_emails(msg_ids, user_email, gmail_service, mongo):
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

            body = detail.get('body', '')

            is_phishing = predict_phishing(body)
            is_spam = True if predict_spam(body) == 1 else False

            email_info = {
                'id': msg_id,
                'subject': detail.get('subject', ''),
                'sender': detail.get('sender', ''),
                'recipients': detail.get('recipients', []),
                'body': body,
                'snippet': detail.get('snippet', ''),
                'has_attachments': detail.get('has_attachments', False),
                'date': formatted_date,
                'time': formatted_time,
                'star': detail.get('star', False),
                'label': label,
                'read': not is_unread,
                'spam': is_spam,
                'phishing': is_phishing
            }
            
            # Store new email in database
            store_email_in_db(email_info, user_email, mongo)
            new_emails.append(email_info)
        except Exception as e:
            logger.error(f"Error processing message ID {msg_id}: {str(e)}")
            continue
    
    return new_emails

def store_email_in_db(email_info, user_email, mongo):
    """Store email info in MongoDB with user reference"""
    try:
        email_info['user_email'] = user_email
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
