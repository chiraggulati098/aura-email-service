from flask import request, jsonify
import logging
from utils.email_utils import process_new_emails, store_email_in_db, sync_emails
from utils.gmail_api import get_email_messages, get_user_email, send_email as gmail_send_email
from flask import request, jsonify

logger = logging.getLogger(__name__)

def register_routes(app, gmail_service, mongo):
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"})

    @app.route("/api/send_email", methods=["POST"])
    def send_email_route():  
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['to', 'subject', 'body']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        try:
            body_type = data.get('body_type', 'plain')
            if body_type not in ['plain', 'html']:
                return jsonify({"error": "body_type must be either 'plain' or 'html'"}), 400

            # Get authenticated user's email
            user_email = get_user_email(gmail_service)
            if not user_email:
                return jsonify({"error": "Could not authenticate user"}), 401

            # Send the email using the imported function
            response = gmail_send_email(
                service=gmail_service,
                to=data['to'],
                subject=data['subject'],
                body=data['body'],
                body_type=body_type
            )

            return jsonify({
                "message": "Email sent successfully",
                "message_id": response['id']
            })

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/sync_emails", methods=["POST"])
    def sync_emails_route():
        user_email = get_user_email(gmail_service)
        if not user_email:
            logger.error("Failed to get user email from Gmail API")
            return jsonify({"error": "Could not authenticate user"}), 401

        try:
            processed_count = sync_emails(gmail_service, user_email, mongo)
            return jsonify({
                "message": "Email sync completed successfully",
                "processed_count": processed_count
            })
        except Exception as e:
            logger.error(f"Error syncing emails: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/fetch_emails", methods=["GET"])
    def fetch_emails():
        EMAILS_PER_PAGE = 20
        page = request.args.get('page', 1, type=int)
        
        user_email = get_user_email(gmail_service)
        if not user_email:
            logger.error("Failed to get user email from Gmail API")
            return jsonify({"error": "Could not authenticate user"}), 401

        try:
            # Calculate skip and limit for pagination
            skip = (page - 1) * EMAILS_PER_PAGE
            
            # Get total count first
            total_emails = mongo.db.emails.count_documents({'user_email': user_email})
            
            # Get paginated emails
            emails = list(mongo.db.emails.find(
                {'user_email': user_email},
                {'_id': 0}
            ).sort([('date', -1), ('time', -1)])
            .skip(skip)
            .limit(EMAILS_PER_PAGE))
            
            # Calculate the range of emails being returned
            start_index = skip + 1
            end_index = min(skip + len(emails), total_emails)
            
            return jsonify({
                'emails': emails,
                'total_emails': total_emails,
                'page': page,
                'emails_per_page': EMAILS_PER_PAGE,
                'start_index': start_index,
                'end_index': end_index
            })
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/refresh", methods=["POST"])
    def refresh_emails():
        user_email = get_user_email(gmail_service)
        if not user_email:
            logger.error("Failed to get user email from Gmail API")
            return jsonify({"error": "Could not authenticate user"}), 401

        try:
            # Call sync_emails to process new emails
            new_emails_count = sync_emails(gmail_service, user_email, mongo)
            needs_refresh = new_emails_count > 0
            
            return jsonify({
                "message": "Refresh completed successfully",
                "new_emails_count": new_emails_count,
                "needs_refresh": needs_refresh
            })
        except Exception as e:
            logger.error(f"Error refreshing emails: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/mark_as_read", methods=["POST"])
    def mark_as_read():
        data = request.json
        if not data or 'msg_id' not in data:
            return jsonify({"error": "Message ID is required"}), 400

        user_email = get_user_email(gmail_service)
        if not user_email:
            logger.error("Failed to get user email from Gmail API")
            return jsonify({"error": "Could not authenticate user"}), 401

        try:
            # Update the email document in MongoDB
            result = mongo.db.emails.update_one(
                {
                    'user_email': user_email,
                    'id': data['msg_id'],  # Using 'id' to match the database schema
                    'read': False  # Only update if it's currently unread
                },
                {'$set': {'read': True}}
            )

            if result.modified_count > 0:
                return jsonify({
                    "message": "Email marked as read successfully",
                    "updated": True
                })
            else:
                return jsonify({
                    "message": "Email was already marked as read or not found",
                    "updated": False
                })
                
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
            return jsonify({"error": str(e)}), 500
