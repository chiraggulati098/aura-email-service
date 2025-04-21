from flask import request, jsonify
import logging
from utils.gemini_api import generate_response

logger = logging.getLogger(__name__)

def register_ai_routes(app, gmail_service, mongo):
    @app.route("/api/summarize_email", methods=["POST"])
    def summarize_email():
        try:
            data = request.json
            if not data or 'msg_id' not in data:
                return jsonify({"error": "Message ID is required"}), 400

            # Get email details from MongoDB
            email = mongo.db.emails.find_one({'id': data['msg_id']})
            if not email:
                email = mongo.db.sent_emails.find_one({'id': data['msg_id']})
            
            if not email:
                return jsonify({"error": "Email not found"}), 404

            # Create the prompt
            prompt = f"""You are an AI assistant tasked with summarizing an email based on the provided details for the recipient's reference. Below is the email content including the subject, sender name, receiver name, body, date, and time. Please generate a concise summary of the email tailored for the recipient, capturing the main points, intent, and any actions required in 2-3 sentences.

Email Details:

Subject: {email.get('subject', 'No subject')}
Sender Name: {email.get('sender', 'No sender')}
Receiver Name: {email.get('recipients', 'No recipients')}
Body: {email.get('body', 'No body')}
Date: {email.get('date', 'No date')}
Time: {email.get('time', 'No time')}

Task: Summarize the email content for the recipient, focusing on the key message, purpose, and any specific actions or responses requested from you. Ensure the summary is clear, professional, and no longer than 3 sentences.
---
Summarized mail:"""

            # Get summary from Gemini
            summary = generate_response(prompt)
            
            return jsonify({
                "message": "Email summarized successfully",
                "summary": summary
            })

        except Exception as e:
            logger.error(f"Error summarizing email: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/generate_reply", methods=["POST"])
    def generate_email_reply():
        try:
            data = request.json
            if not data or 'msg_id' not in data:
                return jsonify({"error": "Message ID is required"}), 400

            # Get email details from MongoDB
            email = mongo.db.emails.find_one({'id': data['msg_id']})
            if not email:
                email = mongo.db.sent_emails.find_one({'id': data['msg_id']})
            
            if not email:
                return jsonify({"error": "Email not found"}), 404

            # Create the prompt
            prompt = f"""You are an AI assistant tasked with drafting the body of a professional email reply from the receiver's perspective based on the provided email details. Below is the email content including the subject, sender name, receiver name, body, date, and time. Please generate a concise and appropriate reply body that addresses the key points, intent, and any actions or questions raised in the original email, without including a subject line.

Email Details:

Subject: {email.get('subject', 'No subject')}
Sender Name: {email.get('sender', 'No sender')}
Receiver Name: {email.get('recipients', 'No recipients')}
Body: {email.get('body', 'No body')}
Date: {email.get('date', 'No date')}
Time: {email.get('time', 'No time')}

Task: Draft the body of a reply email from the receiver to the sender, responding to the main message, acknowledging any requests, and providing relevant answers or actions. Ensure the reply is polite, professional, and concise, maintaining an appropriate tone based on the original email's context. Remember not to add a subject, subject will be prefilled, just give the output as the mail body section for the reply. Also do add a salutation and closing line to the reply, something like warm regards, best regards, etc. depending on the context of the email.

Reply:"""

            # Get reply from Gemini
            reply = generate_response(prompt)
            
            return jsonify({
                "message": "Email reply generated successfully",
                "reply": reply
            })

        except Exception as e:
            logger.error(f"Error generating email reply: {str(e)}")
            return jsonify({"error": str(e)}), 500
