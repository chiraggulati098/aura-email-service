from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
from email.utils import parsedate_to_datetime

from utils.gmail_api import init_gmail_service, get_email_messages, get_email_message_details

app = Flask(__name__)
CORS(app)

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

@app.route("/api/fetch_emails", methods=["GET"])
def fetch_emails():
    messages = get_email_messages(gmail_service, user_id='me', label_ids=None, folder_name='INBOX', max_results=20)
    email_details = []
    
    for msg in messages:
        detail = get_email_message_details(gmail_service, msg['id'])
        
        # Parse the date string
        date_str = detail.get('date', '')
        if date_str:
            parsed_date = parsedate_to_datetime(date_str)
            formatted_date = parsed_date.strftime('%Y-%m-%d')
            formatted_time = parsed_date.strftime('%H:%M:%S')
        else:
            formatted_date = ''
            formatted_time = ''
        
        # Check if message has 'UNREAD' label
        is_unread = 'UNREAD' in detail.get('labelIds', [])
        # Check if message has 'STARRED' label
        is_starred = 'STARRED' in detail.get('labelIds', [])
        
        email_info = {
            'id': msg['id'],
            'subject': detail.get('subject', ''),
            'sender': detail.get('from', ''),
            'recipients': detail.get('to', []),
            'body': detail.get('body', ''),
            'snippet': detail.get('snippet', ''),
            'has_attachments': bool(detail.get('attachments', [])),
            'date': formatted_date,
            'time': formatted_time,
            'star': is_starred,
            'label': detail.get('labelIds', []),
            'read': not is_unread,
            'spam': False,
            'phishing': False
        }
        
        email_details.append(email_info)
    
    return jsonify(email_details)

if __name__ == "__main__":
    client_file = os.path.join(os.path.dirname(__file__), 'client_secret.json')
    gmail_service = init_gmail_service(client_file, api_name='gmail', api_version='v1', scopes=['https://mail.google.com/'])

    app.run(debug=True)