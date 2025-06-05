# AI Restaurant Consulting Platform - Backend

This directory contains the Python backend for the AI Restaurant Consulting Platform, built with FastAPI.

## Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Environment Variables:** Create a `.env` file in this directory with your API keys:
    ```
    # Core API Keys (Required)
    BROWSERBASE_API_KEY=your_browserbase_api_key_here
    BROWSERBASE_PROJECT_ID=your_browserbase_project_id_here
    GOOGLE_API_KEY=your_google_api_key_here
    GEMINI_API_KEY=your_gemini_api_key_here

    # OpenAI (for fallback scraping)
    OPENAI_API_KEY=your_openai_api_key_here

    # Voice & Outreach Services (Optional)
    ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
    TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
    TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
    TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

    # Email & SMS Services (Optional)
    UPCRAFTAI_API_KEY=your_upcraftai_api_key_here
    CUSTOMERIO_API_KEY=your_customerio_api_key_here

    # AWS S3 (for voice message hosting)
    AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
    AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
    AWS_REGION=us-east-1
    S3_BUCKET_NAME=your_s3_bucket_name_here
    ```
4.  **Run the application:**
    ```bash
    uvicorn main:app --reload
    ```