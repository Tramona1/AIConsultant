#!/bin/bash

# Restaurant AI Consulting - Setup Script
# This script sets up the entire application with all dependencies

set -e  # Exit on any error

echo "🍽️  Setting up Restaurant AI Consulting Application"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ] || [ ! -d "backend" ] || [ ! -d "stagehand-scraper" ]; then
    echo "❌ Error: Please run this script from the restaurant-ai-consulting root directory"
    exit 1
fi

echo ""
echo "1️⃣  Installing Frontend Dependencies (Next.js)"
echo "--------------------------------------------"
npm install
echo "✅ Frontend dependencies installed"

echo ""
echo "2️⃣  Installing Stagehand Scraper Dependencies"
echo "--------------------------------------------"
cd stagehand-scraper
npm install
cd ..
echo "✅ Stagehand scraper dependencies installed"

echo ""
echo "3️⃣  Setting up Python Virtual Environment"
echo "-----------------------------------------"
cd backend

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
source .venv/bin/activate
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "4️⃣  Installing Playwright Browsers (for fallback scraping)"
echo "--------------------------------------------------------"
playwright install
echo "✅ Playwright browsers installed"

cd ..

echo ""
echo "5️⃣  Creating necessary directories"
echo "--------------------------------"
mkdir -p backend/menus
mkdir -p backend/analysis_data
echo "✅ Directories created"

echo ""
echo "6️⃣  Environment Configuration"
echo "----------------------------"
if [ ! -f ".env" ]; then
    echo "Creating .env file template..."
    cat > .env << EOF
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
EOF
    echo "✅ .env template created - please update with your API keys"
    echo ""
    echo "⚠️  IMPORTANT: Update the .env file with your actual API keys before running the application!"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "7️⃣  Testing Installations"
echo "-----------------------"

# Test Node.js and npm
echo "Testing Node.js installation..."
node --version
npm --version

# Test Python and pip
echo "Testing Python installation..."
cd backend
source .venv/bin/activate
python --version
pip --version

# Test key dependencies
echo "Testing Stagehand installation..."
cd ../stagehand-scraper
node -e "console.log('Stagehand test:', require('@browserbasehq/stagehand') ? '✅ OK' : '❌ FAILED')"

cd ..
echo "✅ All tests completed"

echo ""
echo "🎉 Setup Complete!"
echo "================="
echo ""
echo "Next steps:"
echo "1. Update the .env file with your actual API keys"
echo "2. Start the backend: cd backend && source .venv/bin/activate && python -m uvicorn main:app --reload"
echo "3. Start the frontend: npm run dev"
echo "4. Visit http://localhost:3000 to use the application"
echo ""
echo "For more information, see the README.md file."
echo ""
echo "Required API Keys:"
echo "• Browserbase: https://browserbase.com (for Stagehand scraping)"
echo "• Google Cloud: https://console.cloud.google.com (for Maps API and Gemini)"
echo "• OpenAI: https://platform.openai.com (for fallback scraping)"
echo ""
echo "Optional API Keys (for outreach features):"
echo "• ElevenLabs: https://elevenlabs.io (for voice messages)"
echo "• Twilio: https://twilio.com (for SMS and voice calls)"
echo "• AWS S3: https://aws.amazon.com/s3/ (for hosting voice files)"
echo "" 