# Aura Email Service

Aura Email Service is a sophisticated email management system that integrates with Gmail API and provides advanced features like email summarization, AI-powered replies, and email classification. The service is built using Flask and MongoDB, with AI capabilities powered by Gemini.

## Architecture

### Core Components

1. **Flask Application (`app.py`)**
   - Main application server
   - Handles CORS configuration
   - Manages MongoDB connection
   - Initializes Gmail service
   - Registers all API routes

2. **Database Layer (MongoDB)**
   - Stores email data
   - Maintains sent emails
   - Uses compound indexes for efficient querying
   - Implements pagination for large datasets

3. **Gmail API Integration**
   - Handles email synchronization
   - Manages email sending
   - Processes email deletion
   - Maintains authentication

4. **AI Integration (Gemini)**
   - Provides email summarization
   - Generates email replies
   - Processes email content

### Directory Structure

```
aura-email-service/
├── app.py                 # Main application file
├── routes/
│   ├── email_routes.py    # Email-related endpoints
│   └── ai_routes.py       # AI-powered endpoints
├── utils/
│   ├── gmail_api.py       # Gmail API utilities
│   ├── email_utils.py     # Email processing utilities
│   └── gemini_api.py      # Gemini AI integration
├── models/                # Data models
├── requirements.txt       # Python dependencies
└── .env                   # Environment variables
```

## API Endpoints

### Email Management

1. **Health Check**
   - `GET /api/health`
   - Returns service status

2. **Send Email**
   - `POST /api/send_email`
   - Required fields: to, subject, body, user_email
   - Optional: body_type (plain/html)

3. **Sync Emails**
   - `POST /api/sync_emails`
   - Required: user_email
   - Synchronizes emails with Gmail

4. **Fetch Emails**
   - `GET /api/fetch_emails`
   - Parameters:
     - page (pagination)
     - filter (all/valid_only/spam_and_phishing)
     - user_email
   - Returns paginated email list

5. **Refresh Emails**
   - `POST /api/refresh`
   - Required: user_email
   - Checks for new emails

6. **Mark as Read**
   - `POST /api/mark_as_read`
   - Required: msg_id, user_email

7. **Delete Email**
   - `POST /api/delete_email`
   - Required: msg_id, user_email

8. **Fetch Sent Emails**
   - `GET /api/fetch_sent_emails`
   - Parameters: page, user_email
   - Returns paginated sent emails

9. **Get User Email**
   - `GET /api/get_user_email`
   - Returns authenticated user's email

### AI Features

1. **Summarize Email**
   - `POST /api/summarize_email`
   - Required: msg_id
   - Returns AI-generated summary

2. **Generate Reply**
   - `POST /api/generate_reply`
   - Required: msg_id
   - Returns AI-generated email reply

## Security Features

- CORS protection with specific origins
- Environment variable configuration
- Secure Gmail API integration
- User-specific data isolation

## Setup and Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables in `.env`:
   - MONGO_URI
   - Gmail API credentials
4. Run the application:
   ```bash
   python app.py
   ```

## Dependencies

- Flask
- Flask-CORS
- Flask-PyMongo
- Google API Client
- Gemini API Client
- Python-dotenv

## Error Handling

The service implements comprehensive error handling:
- Input validation
- API error responses
- Logging system
- Graceful cleanup on exit

## Performance Considerations

- Pagination for large datasets
- Compound indexes for efficient querying
- Background email synchronization
- Caching mechanisms