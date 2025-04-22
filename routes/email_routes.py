from flask import request, jsonify
import logging
from utils.email_utils import process_new_emails, store_email_in_db, sync_emails
from utils.gmail_api import get_email_messages, get_user_email, send_email as gmail_send_email, trash_email
from routes.auth_routes import login_required

logger = logging.getLogger(__name__)

def register_routes(app, mongo):
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"})

    @app.route("/api/send_email", methods=["POST"])
    @login_required
    def send_email_route():  
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['to', 'subject', 'body']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        try:
            gmail_service = request.gmail_service
            body_type = data.get('body_type', 'plain')
            if body_type not in ['plain', 'html']:
                return jsonify({"error": "body_type must be either 'plain' or 'html'"}), 400

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
    @login_required
    def sync_emails_route():
        try:
            gmail_service = request.gmail_service
            user_email = request.user_email
            processed_count = sync_emails(gmail_service, user_email, mongo)
            return jsonify({
                "message": "Email sync completed successfully",
                "processed_count": processed_count
            })
        except Exception as e:
            logger.error(f"Error syncing emails: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/fetch_emails", methods=["GET"])
    @login_required
    def fetch_emails():
        EMAILS_PER_PAGE = 20
        page = request.args.get('page', 1, type=int)
        filter_type = request.args.get('filter', 'all')
        user_email = request.user_email
        
        try:
            # Calculate skip and limit for pagination
            skip = (page - 1) * EMAILS_PER_PAGE
            
            # Base query for user's emails
            base_query = {'user_email': user_email}
            
            # Add classification filter
            if filter_type == 'valid_only':
                base_query.update({'spam': False, 'phishing': False})
            elif filter_type == 'spam_and_phishing':
                base_query.update({'$or': [{'spam': True}, {'phishing': True}]})
            elif filter_type != 'all':
                return jsonify({"error": "Invalid filter type. Must be 'valid_only', 'spam_and_phishing', or 'all'"}), 400
            
            # Get total count first
            total_emails = mongo.db.emails.count_documents(base_query)
            
            # Get paginated emails
            emails = list(mongo.db.emails.find(
                base_query,
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
                'end_index': end_index,
                'filter': filter_type
            })
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/refresh", methods=["POST"])
    @login_required
    def refresh_emails():
        try:
            gmail_service = request.gmail_service
            user_email = request.user_email
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
    @login_required
    def mark_as_read():
        try:
            data = request.json
            if not data or 'msg_id' not in data:
                return jsonify({"error": "Message ID is required"}), 400

            user_email = request.user_email
            result = mongo.db.emails.update_one(
                {
                    'user_email': user_email,
                    'id': data['msg_id'],
                    'read': False
                },
                {'$set': {'read': True}}
            )

            return jsonify({
                "message": "Email marked as read successfully" if result.modified_count > 0 else "Email was already marked as read or not found",
                "updated": result.modified_count > 0
            })
                
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/delete_email", methods=["POST"])
    @login_required
    def delete_email():
        try:
            data = request.json
            if not data or 'msg_id' not in data:
                return jsonify({"error": "Message ID is required"}), 400

            gmail_service = request.gmail_service
            user_email = request.user_email
            gmail_error = None
            
            # Try to delete from Gmail, but continue even if it fails
            try:
                trash_email(gmail_service, data['msg_id'])
            except Exception as gmail_e:
                gmail_error = str(gmail_e)
                logger.error(f"Error deleting email from Gmail: {gmail_error}")

            # Remove the email from MongoDB
            result = mongo.db.emails.delete_one({
                'user_email': user_email,
                'id': data['msg_id']
            })

            if result.deleted_count > 0:
                response = {
                    "message": "Email deleted from database successfully",
                    "deleted": True
                }
                if gmail_error:
                    response["warning"] = f"Email deleted from database but Gmail deletion failed: {gmail_error}"
                return jsonify(response)
            else:
                return jsonify({
                    "message": "Email not found in database",
                    "deleted": False,
                    "warning": gmail_error if gmail_error else None
                })

        except Exception as e:
            logger.error(f"Error deleting email: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/fetch_sent_emails", methods=["GET"])
    @login_required
    def fetch_sent_emails():
        EMAILS_PER_PAGE = 20
        page = request.args.get('page', 1, type=int)
        user_email = request.user_email
        
        try:
            # Calculate skip and limit for pagination
            skip = (page - 1) * EMAILS_PER_PAGE
            
            # Get total count first
            total_emails = mongo.db.sent_emails.count_documents({'user_email': user_email})
            
            # Get paginated sent emails
            emails = list(mongo.db.sent_emails.find(
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
            logger.error(f"Error fetching sent emails: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/get_user_email", methods=["GET"])
    def get_authenticated_user_email():
        try:
            user_email = get_user_email(gmail_service)
            if user_email:
                return jsonify({
                    "email": user_email
                })
            else:
                return jsonify({"error": "Could not retrieve user email"}), 500
        except Exception as e:
            logger.error(f"Error getting user email: {str(e)}")
            return jsonify({"error": str(e)}), 500
