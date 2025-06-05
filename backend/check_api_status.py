#!/usr/bin/env python3
"""
API Status Checker for Restaurant AI Consulting Platform
Helps diagnose API quota and configuration issues
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
import httpx
import openai
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def check_openai_quota():
    """Check OpenAI API quota and billing status"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY not found in environment")
        return False
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Try a simple API call to test quota
        logger.info("🔍 Testing OpenAI API with minimal request...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )
        
        logger.info("✅ OpenAI API: Working (quota available)")
        logger.info(f"📊 Test response: {response.choices[0].message.content}")
        return True
        
    except openai.RateLimitError as e:
        logger.error("❌ OpenAI API: QUOTA EXCEEDED")
        logger.error(f"🔧 Error: {str(e)}")
        logger.error("💡 Solution: Upgrade plan at https://platform.openai.com/usage")
        return False
    except openai.AuthenticationError as e:
        logger.error("❌ OpenAI API: AUTHENTICATION FAILED")
        logger.error(f"🔧 Error: {str(e)}")
        logger.error("💡 Solution: Check your API key at https://platform.openai.com/api-keys")
        return False
    except Exception as e:
        logger.error(f"❌ OpenAI API: Unknown error - {str(e)}")
        return False

async def check_gemini_api():
    """Check Google Gemini API status"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY not found in environment")
        return False
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/Gemini-2.0-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "Test"}]}],
            "generationConfig": {"maxOutputTokens": 5}
        }
        
        logger.info("🔍 Testing Gemini API...")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30)
            
        if response.status_code == 200:
            logger.info("✅ Gemini API: Working")
            return True
        elif response.status_code == 429:
            logger.error("❌ Gemini API: QUOTA EXCEEDED")
            logger.error("💡 Solution: Check quota at https://console.cloud.google.com/")
            return False
        else:
            logger.error(f"❌ Gemini API: HTTP {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Gemini API: Error - {str(e)}")
        return False

async def check_google_maps_api():
    """Check Google Maps API status"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("❌ GOOGLE_API_KEY not found in environment")
        return False
    
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address=1600+Amphitheatre+Parkway,+Mountain+View,+CA&key={api_key}"
        
        logger.info("🔍 Testing Google Maps API...")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "OK":
                logger.info("✅ Google Maps API: Working")
                return True
            elif data.get("status") == "OVER_QUERY_LIMIT":
                logger.error("❌ Google Maps API: QUOTA EXCEEDED")
                logger.error("💡 Solution: Check quota at https://console.cloud.google.com/")
                return False
            else:
                logger.error(f"❌ Google Maps API: Status {data.get('status')}")
                return False
        else:
            logger.error(f"❌ Google Maps API: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Google Maps API: Error - {str(e)}")
        return False

def check_environment_variables():
    """Check all required environment variables"""
    logger.info("🔍 Checking Environment Variables...")
    
    required_vars = {
        "GOOGLE_API_KEY": "Google Maps & Gemini API",
        "GEMINI_API_KEY": "Google Gemini AI",
        "OPENAI_API_KEY": "OpenAI (fallback processing)",
        "BROWSERBASE_API_KEY": "Stagehand scraping",
        "BROWSERBASE_PROJECT_ID": "Stagehand project"
    }
    
    optional_vars = {
        "ELEVENLABS_API_KEY": "Voice generation",
        "TWILIO_ACCOUNT_SID": "SMS/Voice outreach",
        "AWS_ACCESS_KEY_ID": "S3 file storage"
    }
    
    all_good = True
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: Configured ({description})")
        else:
            logger.error(f"❌ {var}: Missing ({description})")
            all_good = False
    
    logger.info("\n📋 Optional Variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: Configured ({description})")
        else:
            logger.warning(f"⚠️ {var}: Not configured ({description})")
    
    return all_good

async def main():
    """Run all API status checks"""
    logger.info("🚀 Restaurant AI Consulting Platform - API Status Check")
    logger.info(f"📅 Check time: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Check environment variables first
    env_ok = check_environment_variables()
    
    logger.info("\n" + "=" * 60)
    logger.info("🌐 Testing API Connections...")
    
    # Test APIs
    apis_status = {}
    apis_status['openai'] = await check_openai_quota()
    apis_status['gemini'] = await check_gemini_api()
    apis_status['google_maps'] = await check_google_maps_api()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 STATUS SUMMARY")
    logger.info("=" * 60)
    
    working_apis = sum(1 for status in apis_status.values() if status)
    total_apis = len(apis_status)
    
    if env_ok and working_apis == total_apis:
        logger.info("🎉 ALL SYSTEMS GO! Your application should work perfectly.")
    elif working_apis >= 2:
        logger.warning(f"⚠️ PARTIAL FUNCTIONALITY: {working_apis}/{total_apis} APIs working")
        logger.warning("Some features may be limited but core functionality should work.")
    else:
        logger.error("🚨 CRITICAL ISSUES: Multiple API failures detected!")
        logger.error("Application may not function properly.")
    
    # Specific recommendations
    logger.info("\n🔧 RECOMMENDATIONS:")
    if not apis_status.get('openai'):
        logger.info("1. Check OpenAI billing: https://platform.openai.com/usage")
        logger.info("2. Consider upgrading OpenAI plan for higher quota")
    
    if not apis_status.get('gemini'):
        logger.info("3. Check Google Cloud billing: https://console.cloud.google.com/")
        logger.info("4. Enable Gemini API in Google Cloud Console")
    
    if not apis_status.get('google_maps'):
        logger.info("5. Check Google Maps API quota and billing")
        logger.info("6. Enable required Google Maps APIs (Places, Geocoding)")
    
    if not env_ok:
        logger.info("7. Update your .env file with missing API keys")
        logger.info("8. Run ./scripts/setup.sh to create .env template")

if __name__ == "__main__":
    asyncio.run(main()) 