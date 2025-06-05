# 🍽️ Restaurant AI Consulting Platform

An AI-powered restaurant analysis and outreach automation platform that provides comprehensive business insights and automated marketing campaigns for restaurants.

## 🌟 Key Features

### Enhanced AI-Powered Data Extraction
- **Stagehand Integration**: Primary scraping using @browserbasehq/stagehand for high-quality, AI-driven data extraction
- **Smart Fallback System**: Multi-layered approach with Playwright + OpenAI and requests fallbacks
- **Comprehensive Data Collection**: Restaurant details, menu items, contact info, social links, business hours, SEO data

### Intelligent Menu Extraction
- **Primary**: Stagehand AI extraction with structured schema validation
- **Fallback**: Gemini-powered HTML analysis when Stagehand data is insufficient
- **Quality Assessment**: Data quality scoring and validation

### Advanced Outreach Automation
- **Multi-Channel**: SMS (UpcraftAI), Email (Customer.io), Voice calls (ElevenLabs + Twilio)
- **S3 Audio Hosting**: Automated upload of voice messages to AWS S3
- **Personalized Content**: AI-generated outreach based on restaurant analysis

### Robust Architecture
- **Enhanced Error Handling**: Comprehensive logging and graceful fallbacks
- **Health Monitoring**: `/health` endpoint with service status checks
- **Data Quality Metrics**: Detailed scoring of extraction success

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.9+
- Required API keys (see Environment Variables section)

### Installation

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd restaurant-ai-consulting
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

2. **Configure environment variables:**
   ```bash
   # Update .env file with your API keys
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

3. **Start the application:**
   ```bash
   # Terminal 1: Backend
   cd backend
   source .venv/bin/activate
   python -m uvicorn main:app --reload

   # Terminal 2: Frontend
   npm run dev
   ```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## 🔧 Environment Variables

### Required (Core Functionality)
```env
BROWSERBASE_API_KEY=your_browserbase_api_key_here
BROWSERBASE_PROJECT_ID=your_browserbase_project_id_here
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### Optional (Enhanced Features)
```env
# Voice & Outreach Services
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

# Email & SMS Services
UPCRAFTAI_API_KEY=your_upcraftai_api_key_here
CUSTOMERIO_API_KEY=your_customerio_api_key_here

# AWS S3 (for voice message hosting)
AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_s3_bucket_name_here
```

## 🏗️ Architecture Overview

### Data Flow
1. **Frontend Request** → FastAPI backend
2. **Stagehand Scraping** → Node.js scraper with Browserbase
3. **Data Transformation** → Python processing and validation
4. **Fallback Processing** → Playwright + OpenAI if needed
5. **Google APIs** → Reviews and competitor data
6. **AI Analysis** → Gemini-powered insights
7. **Outreach Automation** → Multi-channel campaigns

### Enhanced Components

#### 1. Stagehand Integration (`stagehand-scraper/`)
- **enhanced-scraper.js**: Comprehensive Node.js scraper using Stagehand
- **Enhanced Schema**: Validates 7+ data fields with quality scoring
- **Error Handling**: Robust error logging and graceful failures

#### 2. Python Backend (`backend/`)
- **main.py**: Enhanced FastAPI with health checks and better CORS
- **stagehand_integration.py**: Python wrapper for Node.js scraper
- **restaurant_data_aggregator_module.py**: Smart menu extraction logic
- **outreach_automation_module.py**: Complete S3 + ElevenLabs integration

#### 3. Key Improvements
- **Menu Extraction Priority**: Stagehand first, Gemini fallback only if needed
- **Screenshot Handling**: Proper path management for cross-environment access
- **S3 Audio Upload**: Complete implementation with public URL generation
- **Data Quality Assessment**: 7-field scoring system
- **Enhanced Logging**: Emoji-based logging for better readability

## 📊 Data Quality Metrics

The system now tracks extraction success across 7 key areas:
- ✅ Restaurant Name
- ✅ Contact Information (email/phone)
- ✅ Address
- ✅ Menu Items
- ✅ Social Media Links
- ✅ Business Hours
- ✅ Restaurant Type/Cuisine

## 🔍 API Endpoints

### Core Analysis
- `POST /api/v1/analyze-restaurant/` - Analyze restaurant from URL
- `GET /api/v1/report/{report_id}` - Retrieve full analysis report

### Outreach
- `POST /api/v1/trigger-outreach/` - Trigger outreach campaigns

### Monitoring
- `GET /health` - Service health and status check
- `GET /` - API information and version

## 🛠️ Development

### Testing Stagehand Integration
```bash
cd stagehand-scraper
node enhanced-scraper.js https://restaurant-website.com
```

### Testing Python Components
```bash
cd backend
source .venv/bin/activate
python test_stagehand.py
python test_fallback_scraper.py
```

### Debugging
- **Logs**: Check `backend/app.log` for detailed application logs
- **Health Check**: Visit `/health` endpoint for service status
- **Stagehand Logs**: Check `stagehand-scraper/scraper.log`

## 🔐 Security Considerations

- API keys stored in environment variables
- CORS properly configured for frontend/backend communication
- File uploads sanitized and validated
- Temporary files cleaned up after S3 upload

## 📈 Performance Optimizations

- **Parallel Processing**: Google APIs called concurrently
- **Smart Caching**: Stagehand caching enabled
- **Memory Management**: HTML content cleaned after processing
- **Timeout Handling**: 2-minute timeout for scraping operations

## 🤖 AI Services Integration

### Stagehand (Primary Scraper)
- **Provider**: Browserbase
- **Features**: AI-powered extraction, schema validation, caching
- **Fallback**: Playwright + OpenAI

### Gemini (Analysis & Fallback)
- **Provider**: Google Cloud
- **Features**: Restaurant analysis, menu extraction fallback
- **Models**: Gemini 2.5 Flash

### ElevenLabs (Voice)
- **Provider**: ElevenLabs
- **Features**: Voice message generation
- **Integration**: S3 upload + Twilio delivery

## 📝 Logging

Enhanced logging with emojis for better readability:
- 🚀 Application startup
- 🔍 Analysis requests
- 📊 Data aggregation
- 🧠 LLM analysis
- 💾 Data storage
- 📞 Outreach campaigns
- ❌ Errors and warnings

## 📦 Dependencies

### Frontend
- Next.js 15.3.2
- React 19.0.0
- Tailwind CSS 4
- Framer Motion
- Recharts

### Backend
- FastAPI 0.111.0
- Stagehand 2.2.1
- ElevenLabs 1.7.0
- Playwright 1.52.0
- OpenAI 1.82.1

### Node.js Scraper
- @browserbasehq/stagehand 2.2.1
- zod 3.25.42
- dotenv 16.5.0

## 🚨 Troubleshooting

### Common Issues

1. **Stagehand Not Available**
   - Check `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID`
   - Ensure Node.js dependencies installed: `cd stagehand-scraper && npm install`

2. **Menu Extraction Failing**
   - System automatically falls back to Gemini if Stagehand fails
   - Check logs for specific error messages

3. **Voice Calls Not Working**
   - Verify ElevenLabs API key
   - Ensure AWS S3 credentials configured
   - Check Twilio credentials and phone number

4. **Health Check Failing**
   - Visit `/health` endpoint to see specific service status
   - Check logs for detailed error information

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `npm test` and `python -m pytest`
4. Submit a pull request

## 📞 Support

For issues and questions:
- Check the `/health` endpoint for service status
- Review logs in `backend/app.log`
- Open an issue on GitHub

---

Built with ❤️ for the restaurant industry, powered by cutting-edge AI technology.
