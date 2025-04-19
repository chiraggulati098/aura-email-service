import logging
from email.utils import parsedate_to_datetime
from utils.gmail_api import get_email_message_details

logger = logging.getLogger(__name__)

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
